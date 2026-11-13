#include "robot_gate/control_gate.hpp"
#include <limits>
namespace robot_gate {
namespace { constexpr Id maximum = std::numeric_limits<Id>::max(); }
ControlGate::ControlGate(const Config& c) noexcept : config_(c) {
    if (c.boot==0 || c.profile==0 || c.count<1 || c.count>2 ||
        (c.count==1 && c.axes[0]!=1 && c.axes[0]!=2) ||
        (c.count==2 && (c.axes[0]!=1 || c.axes[1]!=2))) stop(0,Error::ConfigInvalid,true);
}
void ControlGate::clear() noexcept {
    owner_=lease_=lease_until_=ticket_=ticket_until_=ticket_revision_=0;
    armed_=0; reserved_=dispatched_=pending_=false; intent_={};
}
void ControlGate::stop(Id now, Error e, bool f) noexcept {
    if (!stopping_) { stop_at_=now; stop_pending_=true; }
    if (!stopping_ || (f && !fault_)) error_=e;
    stopping_=true; fault_=fault_||f; clear();
}
bool ControlGate::deadline(Id now, Id duration, Id& out) noexcept {
    if (now>maximum-duration) { stop(now,Error::Overflow,true); return false; }
    out=now+duration; return true;
}
Id ControlGate::allocate(Id now) noexcept {
    if (next_id_==maximum) { stop(now,Error::IdentityExhausted,true); return 0; }
    return next_id_++;
}
bool ControlGate::same(const Snapshot& s) const noexcept {
    if (s.profile!=snapshot_.profile || s.count!=snapshot_.count || s.approved!=snapshot_.approved ||
        s.ready!=snapshot_.ready || s.stopped!=snapshot_.stopped || s.moving!=snapshot_.moving ||
        s.stop!=snapshot_.stop || s.fault!=snapshot_.fault) return false;
    for (unsigned i=0;i<2;++i) if (s.axes[i].id!=snapshot_.axes[i].id || s.axes[i].valid!=snapshot_.axes[i].valid ||
        s.axes[i].enabled!=snapshot_.axes[i].enabled || s.axes[i].moving!=snapshot_.axes[i].moving) return false;
    return true;
}
bool ControlGate::healthy() const noexcept {
    if (!seen_snapshot_ || !snapshot_.approved || snapshot_.stop || snapshot_.fault) return false;
    for (unsigned i=0;i<config_.count;++i) if (!snapshot_.axes[i].valid) return false;
    return true;
}
bool ControlGate::stopped() const noexcept { return healthy() && snapshot_.ready && snapshot_.stopped && !snapshot_.moving; }
bool ControlGate::enabled(std::uint16_t a) const noexcept {
    for (unsigned i=0;i<config_.count;++i) if (snapshot_.axes[i].id==a) return snapshot_.axes[i].enabled;
    return false;
}
bool ControlGate::end_guard(Id now) noexcept {
    if (stopping_) return false;
    if (owner_!=0 && now>=lease_until_) { stop(now,Error::Expired); return false; }
    if ((pending_ || dispatched_) && (!reserved_ || intent_.lease!=lease_ || intent_.axis!=armed_)) {
        stop(now,Error::SnapshotInvalid,true); return false;
    }
    return true;
}
bool ControlGate::advance(Id now, const Snapshot& s) noexcept {
    if (seen_time_ && now<last_now_) { stop(now,Error::ClockReversed,true); return false; }
    seen_time_=true; last_now_=now;
    if (s.profile!=config_.profile || s.count!=config_.count) { stop(now,Error::ProfileChanged,true); return false; }
    bool moving=false;
    for (unsigned i=0;i<config_.count;++i) {
        if (s.axes[i].id!=config_.axes[i]) { stop(now,Error::ProfileChanged,true); return false; }
        moving=moving||s.axes[i].moving;
    }
    if (s.revision==0 || s.revision==maximum || s.moving!=moving || (s.stopped && moving) ||
        (seen_snapshot_ && (s.revision<snapshot_.revision || (s.revision==snapshot_.revision && !same(s))))) {
        stop(now,Error::SnapshotInvalid,true); return false;
    }
    const bool changed=seen_snapshot_ && s.revision!=snapshot_.revision;
    snapshot_=s; seen_snapshot_=true;
    if (stopping_) return false;
    if (s.stop || s.fault) { stop(now,Error::Stopping,s.fault); return false; }
    if (owner_!=0 && now>=lease_until_) { stop(now,Error::Expired); return false; }
    if ((armed_!=0 || reserved_) && !healthy()) { stop(now,Error::Denied); return false; }
    if (armed_!=0 || reserved_) {
        for (unsigned i=0;i<config_.count;++i) if (s.axes[i].moving && (!dispatched_ || s.axes[i].id!=armed_)) {
            stop(now,Error::Denied); return false;
        }
    }
    if (pending_ && (changed || now>=intent_.dispatch_before || !stopped() || !enabled(armed_))) {
        stop(now,Error::Expired); return false;
    }
    if (!dispatched_ && armed_!=0 && !stopped()) { stop(now,Error::Denied); return false; }
    if (changed && !reserved_) { ticket_=0; armed_=0; }
    if (ticket_!=0 && now>=ticket_until_) ticket_=0;
    return end_guard(now);
}
Id ControlGate::open_session(Id now,const Snapshot& s) noexcept {
    if (!advance(now,s)) return 0;
    for (auto& session:sessions_) if (session.id==0) { session.id=allocate(now); return session.id; }
    error_=Error::SessionFull; return 0;
}
void ControlGate::close_session(Id now,const Snapshot& s,Id id) noexcept {
    advance(now,s);
    if (id==0) return;
    for (auto& session:sessions_) if (session.id==id) { session={}; if (owner_==id) stop(now,Error::Stopping); return; }
}
Result ControlGate::handle(Id now,const Snapshot& s,const Request& r) noexcept {
    const bool active=advance(now,s);
    auto fail=[this](Error e) { if (!stopping_) error_=e; return Result{e,0,0}; };
    if (r.boot!=config_.boot) return fail(Error::BadBoot);
    Session* session=nullptr;
    for (auto& item:sessions_) if (r.session!=0 && item.id==r.session) session=&item;
    if (session==nullptr) return fail(Error::BadSession);
    if (r.op==Op::Stop) { stop(now,Error::Stopping); return {Error::None,0,0}; }
    if (!active) return fail(error_);
    if (r.seq==0 || r.request==0 || r.seq<=session->seq || r.request<=session->request) return fail(Error::Replay);
    if (r.seq==maximum || r.request==maximum) { stop(now,Error::IdentityExhausted,true); return fail(error_); }
    session->seq=r.seq; session->request=r.request;
    if (static_cast<unsigned>(r.op)>static_cast<unsigned>(Op::Stop)) return fail(Error::BadRequest);
    if (r.op==Op::Acquire) {
        if (owner_!=0 || reserved_) return fail(Error::Busy);
        if (!stopped()) return fail(Error::Denied);
        if (!deadline(now,800,lease_until_)) return fail(error_);
        lease_=allocate(now); if (lease_==0) return fail(error_);
        owner_=r.session; error_=Error::None; return {Error::None,lease_,0};
    }
    if (owner_!=r.session || r.lease==0 || r.lease!=lease_) return fail(Error::BadLease);
    if (r.op==Op::Renew) {
        if (!deadline(now,800,lease_until_)) return fail(error_);
    } else if (r.op==Op::Release) {
        stop(now,Error::Stopping);
    } else if (r.op==Op::Arm) {
        if (reserved_) return fail(Error::Busy);
        if (!stopped() || !enabled(r.axis) || (armed_!=0 && armed_!=r.axis)) return fail(Error::AxisDenied);
        armed_=r.axis;
    } else if (r.op==Op::Ticket) {
        if (reserved_ || ticket_!=0) return fail(Error::Busy);
        if (!stopped() || armed_==0 || r.axis!=armed_ || !enabled(armed_)) return fail(Error::AxisDenied);
        if (!deadline(now,500,ticket_until_)) return fail(error_);
        ticket_=allocate(now); if (ticket_==0) return fail(error_);
        ticket_revision_=snapshot_.revision;
        error_=Error::None; return {Error::None,lease_,ticket_};
    } else if (r.op==Op::Move) {
        if (reserved_) return fail(Error::Busy);
        if (!stopped() || !enabled(armed_) || armed_==0 || r.axis!=armed_) return fail(Error::AxisDenied);
        if (r.direction>1) return fail(Error::BadRequest);
        if (ticket_==0 || r.ticket!=ticket_ || ticket_revision_!=snapshot_.revision || now>=ticket_until_) return fail(Error::BadTicket);
        const Id id=allocate(now); if (id==0) return fail(error_);
        intent_={id,config_.boot,owner_,lease_,snapshot_.revision,
                 ticket_until_<lease_until_?ticket_until_:lease_until_,armed_,100,r.direction,5,2};
        ticket_=0; reserved_=pending_=true;
    }
    if (!stopping_) { error_=Error::None; end_guard(now); }
    return {Error::None,lease_,0};
}
void ControlGate::tick(Id now,const Snapshot& s) noexcept { advance(now,s); }
bool ControlGate::take_intent(Id now,const Snapshot& s,Intent& out) noexcept {
    out={};
    if (!advance(now,s) || !pending_) return false;
    // Keep a separate consumption deadline guard: queued work cannot outlive its permit.
    if (now>=intent_.dispatch_before) { stop(now,Error::Expired); return false; }
    out=intent_; pending_=false; dispatched_=true; return end_guard(now);
}
bool ControlGate::take_stop(Id now,const Snapshot& s,Id& at) noexcept {
    advance(now,s); if (!stop_pending_) return false;
    at=stop_at_; stop_pending_=false; return true;
}
bool ControlGate::complete(Id now,const Snapshot& s,Id id) noexcept {
    if (!advance(now,s)) return false;
    if (!dispatched_ || id==0 || id!=intent_.id || snapshot_.revision<=intent_.revision || !stopped() || !enabled(armed_)) {
        stop(now,Error::CompletionInvalid); return false;
    }
    reserved_=dispatched_=pending_=false; intent_={}; armed_=0; return end_guard(now);
}
Status ControlGate::status() const noexcept {
    return {error_,snapshot_.revision,owner_,lease_,lease_until_,stop_at_,armed_,stopping_,fault_,reserved_,dispatched_};
}
} // namespace robot_gate
