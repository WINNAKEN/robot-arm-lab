#include "robot_run/bench_run.hpp"
#include <limits>
namespace robot_run {
bool BenchRun::position_sample(unsigned axis,std::int64_t& value,Time& tx_at,Time& at)const noexcept{value=0;tx_at=at=0;if(profile_.gate.count==0||profile_.gate.count>proofs_.size()||axis>=proofs_.size()||axis>=profile_.gate.count)return false;const auto& s=proofs_[axis].sample[1];value=s.value;tx_at=s.tx;at=s.at;return s.valid;}
Time BenchRun::oldest_configuration_at()const noexcept{if(profile_.gate.count==0||profile_.gate.count>configurations_.size())return 0;Time oldest=~Time{0};for(unsigned a=0;a<profile_.gate.count;++a)for(const auto& s:configurations_[a]){if(!s.valid)return 0;if(s.dequeued_at<oldest)oldest=s.dequeued_at;}return oldest==~Time{0}?0:oldest;}
using namespace robot_can;
namespace {constexpr std::array<std::uint8_t,4> codes{0xF1,0x31,0x32,0x3A}; constexpr Time max_time=std::numeric_limits<Time>::max();}
BenchRun::BenchRun(CanPort& p,const Profile& profile) noexcept : port_(p),profile_(profile),gate_(profile.gate),stop_(p) {
    snapshot_.profile=profile.gate.profile; snapshot_.count=profile.gate.count; snapshot_.revision=1;
    for(unsigned i=0;i<2;++i) snapshot_.axes[i].id=profile.gate.axes[i];
}
bool BenchRun::expected_enabled(unsigned a) const noexcept { return profile_.enable_policy==EnablePolicy::LegacyAllEnabled || profile_.gate.axes[a]==profile_.selected_axis; }
std::uint32_t BenchRun::expected_configuration(unsigned a,unsigned c) const noexcept {
    switch(c){case 0:return 5;case 1:return 16;case 2:return 2;case 3:return profile_.gate.axes[a];case 4:return 0x101;case 5:return 0;default:return 1000;}
}
bool BenchRun::configuration_sample(unsigned a,unsigned c,robot_config::ConfigSample& out) const noexcept {
    out={};if(!boot_approved_ || a>=profile_.gate.count || c>=7)return false;out=configurations_[a][c];return out.valid;
}
bool BenchRun::configurations_fresh(Time now) const noexcept {
    if(!boot_approved_)return true;
    for(unsigned a=0;a<profile_.gate.count;++a)for(unsigned c=0;c<7;++c){const auto& s=configurations_[a][c];
        if(s.value!=expected_configuration(a,c) || !robot_config::sample_fresh(s,now))return false;}
    return true;
}
bool BenchRun::configuration_headroom(Time now,Time margin) const noexcept {
    if(!boot_approved_)return true;
    if(now>max_time-margin)return false;
    for(unsigned a=0;a<profile_.gate.count;++a)for(const auto& s:configurations_[a])if(!robot_config::sample_headroom(s,now,margin))return false;
    return true;
}
bool BenchRun::active() const noexcept {return status_.state!=State::Idle && status_.state!=State::Stopping && status_.state!=State::Fault && status_.state!=State::StoppedRecheck;}
bool BenchRun::add(Time b,Time d,Time& out) noexcept {if(b>max_time-d){enter_stop(Fault::Overflow);return false;}out=b+d;return true;}
void BenchRun::record(const RxFrame& r) noexcept {raw_[raw_head_]=r;raw_head_=(raw_head_+1)%raw_.size();if(raw_size_<raw_.size())++raw_size_;else if(raw_dropped_<max_time)++raw_dropped_;}
int BenchRun::code_index(std::uint8_t c) noexcept {for(unsigned i=0;i<4;++i)if(c==codes[i])return static_cast<int>(i);return -1;}
void BenchRun::emergency(Fault f) noexcept {
    if(status_.fault==Fault::None){status_.fault=f;status_.fault_at=port_.now_ms();}
    if(touched_ && !stop_.close_attempted())status_.closed=port_.close();
    else if(stop_.close_attempted())status_.closed=stop_.close_result();
    status_.state=State::Fault;status_.torque_unknown=status_.manual_power_cut_required=true;
}
void BenchRun::stop_poll(bool begin_stop) noexcept {
    const auto before=port_.now_ms();
    if(before<last_clock_ || before>=stop_until_ || (!preparation_seen_ && before>=prep_until_)) {emergency(Fault::StopTiming);return;}
    if(begin_stop && (before-status_.stop_at>=10 || before>=isolation_until_)){emergency(Fault::StopTiming);return;}
    last_clock_=before;
    if(begin_stop)stop_.begin_stop(profile_.stop); else stop_.poll();
    const auto now=port_.now_ms();
    if(now<before || now-before>=10 || now>=stop_until_ || (begin_stop && now>=isolation_until_)){emergency(Fault::StopTiming);return;}
    last_clock_=now;
    const auto phase=stop_.core().state();
    const bool past=phase==robot_core::StopState::Quiet || phase==robot_core::StopState::Verifying || phase==robot_core::StopState::StoppedRecheck;
    if(!preparation_seen_ && past){if(now>=prep_until_){emergency(Fault::StopTiming);return;}preparation_seen_=true;status_.preparation_at=now;}
    if(!preparation_seen_ && now>=prep_until_){emergency(Fault::StopTiming);return;}
    if(stop_.state()==LinkState::Fault){status_.closed=stop_.close_result();emergency(Fault::Port);return;}
    if(stop_.state()==LinkState::StoppedRecheck){
        status_.closed=stop_.close_result();status_.stop_verified=preparation_seen_ && status_.closed.healthy && status_.closed.quiesced;
        if(!status_.stop_verified){emergency(Fault::Cleanup);return;}
        status_.state=status_.fault==Fault::None?State::StoppedRecheck:State::Fault;
    }
}
void BenchRun::enter_stop(Fault f) noexcept {
    if(status_.state==State::Fault || status_.state==State::StoppedRecheck)return;
    const auto now=port_.now_ms();
    if(f!=Fault::None && status_.fault==Fault::None){status_.fault=f;status_.fault_at=now;}
    if(status_.state==State::Stopping)return;
    const auto gs=gate_.status(); status_.stop_at=gs.stopped_latched && gs.stop_started_at<=now?gs.stop_started_at:now;
    status_.state=State::Stopping;inflight_=false;read_={};move_={};
    if(snapshot_.revision==max_time){emergency(Fault::Overflow);return;}
    ++snapshot_.revision;snapshot_.stop=true;snapshot_.ready=false;snapshot_.stopped=false;
    gate_.tick(now,snapshot_);
    // A known bus fault invalidates the borrowed unchanged-driver heartbeat premise.
    // The historical legacy fixture policy stays separate; never reset it into new proof.
    if(profile_.enable_policy==EnablePolicy::SingleSelected && (f==Fault::Bus || f==Fault::ConfigMismatch || premise_invalidated_)){
        status_.stop_verified=false;emergency(f);return;
    }
    if(status_.stop_at>max_time-3600){emergency(Fault::Overflow);return;}
    stop_until_=status_.stop_at+3600;prep_until_=status_.stop_at+600;isolation_until_=status_.stop_at+100;
    stop_poll(true);
}
bool BenchRun::time_ok() noexcept {
    if(!active())return false;
    const auto now=port_.now_ms();
    if(saw_clock_ && now<last_clock_){enter_stop(Fault::Clock);return false;}
    if(now<operation_at_ || now-operation_at_>=10){enter_stop(Fault::Service);return false;}
    saw_clock_=true;last_clock_=now;return true;
}
bool BenchRun::fresh(unsigned a,unsigned c,Time after) const noexcept {
    const auto& s=proofs_[a].sample[c];const auto now=port_.now_ms();
    return s.valid && now>=s.at && now-s.at<400 && s.tx>=after;
}
bool BenchRun::proof(bool post) const noexcept {
    const auto after=post?completed_at_+1:Time{0};
    for(unsigned a=0;a<profile_.gate.count;++a){
        for(unsigned c=0;c<4;++c)if(!fresh(a,c,after))return false;
        const auto& p=proofs_[a];if(p.sample[0].value!=1 || p.sample[2].value!=0 || p.sample[3].value!=(expected_enabled(a)?1:0) || p.positions_count<3)return false;
        auto lo=p.positions[0].value,hi=lo;
        for(unsigned i=0;i<3;++i){const auto& s=p.positions[i];if(!s.valid || s.tx<after || port_.now_ms()<s.at || port_.now_ms()-s.at>=400)return false;if(i && (s.tx<p.positions[i-1].tx || s.tx-p.positions[i-1].tx<140))return false;if(s.value<lo)lo=s.value;if(s.value>hi)hi=s.value;}
        if(static_cast<std::uint64_t>(hi-lo)>profile_.stop.tolerance_counts)return false;
    }
    if(post){int sign=profile_.dir0_sign;if(move_.direction==1)sign=-sign;
        unsigned a=move_.axis==profile_.gate.axes[0]?0:1;
        const auto delta=proofs_[a].sample[1].value-baseline_;
        if(delta==0 || (sign>0 && delta<0) || (sign<0 && delta>0))return false;
        const auto expected=static_cast<std::int64_t>(profile_.counts_per_100pulse)*sign;
        const auto difference=delta>expected?delta-expected:expected-delta;
        if(static_cast<std::uint64_t>(difference)>profile_.stop.tolerance_counts)return false;
    }
    return true;
}
void BenchRun::publish(bool ready) noexcept {
    if(snapshot_.revision>=max_time-1){enter_stop(Fault::Overflow);return;}
    ++snapshot_.revision;snapshot_.approved=true;snapshot_.ready=ready;snapshot_.stopped=ready;snapshot_.moving=false;
    const bool moving=status_.state==State::AwaitStart || status_.state==State::Moving || status_.state==State::Completing;
    for(unsigned a=0;a<profile_.gate.count;++a){auto& ax=snapshot_.axes[a];ax.valid=true;for(unsigned c=0;c<4;++c)ax.valid=ax.valid&&fresh(a,c);ax.enabled=fresh(a,3)&&proofs_[a].sample[3].value==1;ax.moving=moving&&ax.id==move_.axis;snapshot_.moving=snapshot_.moving||ax.moving;}
    if(moving)snapshot_.stopped=false;
}
void BenchRun::sync_gate() noexcept {
    if(!active())return;
    gate_.tick(port_.now_ms(),snapshot_);
    const auto s=gate_.status();if(s.stopped_latched)enter_stop(s.fault?Fault::Gate:Fault::None);
}
bool BenchRun::deadlines() noexcept {
    if(!time_ok())return false;
    const auto now=port_.now_ms();
    if(!configurations_fresh(now) || (authority_until_!=0 && now>=authority_until_)){enter_stop(Fault::Profile);return false;}
    if(status_.state==State::Checking && now>=checking_until_){enter_stop(Fault::Observation);return false;}
    if(inflight_ && now>=tx_deadline_){enter_stop(Fault::Tx);return false;}
    if(read_.active && read_.confirmed && now>=read_.deadline){enter_stop(Fault::Deadline);return false;}
    if(move_.id!=0 && move_until_!=0 && (now>=move_until_ || (!started_ && now>=start_until_))){enter_stop(Fault::Deadline);return false;}
    if(ever_ready_){for(unsigned a=0;a<profile_.gate.count;++a)for(unsigned c=0;c<4;++c)if(!fresh(a,c)){enter_stop(Fault::Observation);return false;}}
    sync_gate();return active();
}
void BenchRun::begin_from_boot(BootEvidence&& e) noexcept {
    const bool had=e.valid_;e.valid_=false;
    const auto now=port_.now_ms();const auto& p=e.profile_;const auto& c=profile_.gate;
    bool match=p.gate.boot==c.boot && p.gate.profile==c.profile && p.gate.count==c.count && p.gate.axes==c.axes && p.selected_axis==profile_.selected_axis && p.counts_per_100pulse==profile_.counts_per_100pulse && p.dir0_sign==profile_.dir0_sign && p.stop.tolerance_counts==profile_.stop.tolerance_counts;
    if(begun_ || !had || e.port_!=&port_ || !match || profile_.enable_policy!=EnablePolicy::SingleSelected || e.principal_==0 || now>=e.admit_ || now>=e.config_ || now>=e.authority_){status_.fault=Fault::Profile;status_.state=State::Fault;status_.torque_unknown=status_.manual_power_cut_required=true;begun_=true;return;}
    configurations_=e.settings_;boot_approved_=true;
    if(!configurations_fresh(now)){status_.fault=Fault::Profile;status_.fault_at=now;status_.state=State::Fault;status_.torque_unknown=status_.manual_power_cut_required=true;begun_=true;return;}
    for(unsigned a=0;a<c.count;++a)for(unsigned index=0;index<7;++index)last_config_[a][index]=configurations_[a][index].tx_at;
    profile_.stop.heartbeat_1000_readback_confirmed=true;
    principal_=e.principal_;authority_until_=e.authority_;begin();
}
void BenchRun::begin() noexcept {
    if(begun_)return;
    begun_=true;
    const auto& p=profile_;const auto& c=p.gate;
    bool selected_valid=profile_.enable_policy==EnablePolicy::LegacyAllEnabled;
    if(profile_.enable_policy==EnablePolicy::SingleSelected){for(unsigned a=0;a<c.count && a<2;++a)if(c.axes[a]==p.selected_axis)selected_valid=true;selected_valid=selected_valid&&boot_approved_;}
    if(!selected_valid || gate_.status().fault || !p.normal_approved || (!p.post_maintenance_enable_seed_approved && !boot_approved_) || !p.stop.heartbeat_1000_readback_confirmed || !p.stop.response_bounds_approved || !p.stop.position_tolerance_approved || p.stop.axis_count!=c.count || p.counts_per_100pulse==0 || p.counts_per_100pulse>(Time{1}<<40) || p.stop.tolerance_counts>(Time{1}<<32) || (p.dir0_sign!=1 && p.dir0_sign!=-1)) {status_.fault=Fault::Profile;status_.state=State::Fault;status_.torque_unknown=status_.manual_power_cut_required=true;return;}
    for(unsigned a=0;a<c.count;++a)if(p.stop.axes[a]!=c.axes[a]){status_.fault=Fault::Profile;status_.state=State::Fault;status_.torque_unknown=status_.manual_power_cut_required=true;return;}
    status_.state=State::Checking;operation_at_=last_clock_=last_poll_=port_.now_ms();saw_clock_=true;
    if(!add(last_clock_,2000,checking_until_))return;
    touched_=true;if(!port_.reset_and_start()){enter_stop(Fault::Port);return;}
    if(!time_ok())return;
    last_poll_=port_.now_ms();next_read_=last_poll_;
}
bool BenchRun::health(bool empty) noexcept {
    std::uint32_t alerts=0;PortStatus s;
    if(!port_.read_alerts(alerts)||!port_.status(s)){enter_stop(Fault::Port);return false;}
    if(s.state!=BusState::Running || !error_counters_clear(s) || (alerts&fatal_alerts) || (alerts&~all_alerts)){premise_invalidated_=true;enter_stop(Fault::Bus);return false;}
    if(!deadlines())return false;
    if(s.rx_pending>16 || (empty&&s.rx_pending!=0)){enter_stop(Fault::Rx);return false;}
    if(s.tx_pending>1 || (s.tx_pending!=0&&!inflight_)){enter_stop(Fault::Tx);return false;}
    const auto terminal=alerts&(TxSuccess|TxFailed);
    if(terminal){if(!inflight_ || s.tx_pending!=0 || terminal!=(TxSuccess)){enter_stop(Fault::Tx);return false;}
        inflight_=false;const auto now=port_.now_ms();
        if(tx_move_){if(!add(now,2000,move_until_)||!add(now,200,start_until_))return false;}
        else {read_.confirmed=true;read_.tx=now;if(read_.configuration)last_config_[read_.axis][read_.code]=now;else last_read_[read_.axis][read_.code]=now;if(!add(now,100,read_.deadline))return false;}
    }
    return true;
}
bool BenchRun::submit(const robot_core::mks::Frame& f,Time before,unsigned a,unsigned c,bool moving,bool configuration) noexcept {
    if(!health(true)||!deadlines()||inflight_ || port_.now_ms()>=before)return false;
    const auto now=port_.now_ms();if(!add(now,50,tx_deadline_))return false;
    if(before<tx_deadline_)tx_deadline_=before;
    inflight_=true;tx_move_=moving;
    if(!moving)read_={true,false,a,c,0,0,configuration};
    WireFrame w{f.id,f.dlc,f.data,f.extended,f.rtr};
    if(!port_.submit(w,before)){enter_stop(Fault::Tx);return false;}
    if(!time_ok())return false;
    if(port_.now_ms()>=before){enter_stop(Fault::Tx);return false;}
    return true;
}
void BenchRun::receive(const RxFrame& rx) noexcept {
    record(rx);if(!deadlines())return;
    if(rx.frame.id>0x7ff || rx.dequeued_at>port_.now_ms() || port_.now_ms()-rx.dequeued_at>=10)return;
    robot_core::mks::Frame f{static_cast<std::uint16_t>(rx.frame.id),rx.frame.dlc,rx.frame.data,rx.frame.extended,rx.frame.rtr};
    if(read_.active && read_.configuration && read_.confirmed && f.id==profile_.gate.axes[read_.axis] && f.data[0]==robot_config::settings[read_.code] && rx.dequeued_at>=read_.tx && rx.dequeued_at<read_.deadline){
        const auto parsed_config=robot_config::parse_config(f,robot_config::settings[read_.code]);
        if(parsed_config.error==robot_config::DecodeError::Unsupported){premise_invalidated_=true;enter_stop(Fault::ConfigMismatch);return;}
        if(parsed_config.error!=robot_config::DecodeError::None)return;
        if(parsed_config.value!=expected_configuration(read_.axis,read_.code)){premise_invalidated_=true;enter_stop(Fault::ConfigMismatch);return;}
        configurations_[read_.axis][read_.code]={true,parsed_config.value,read_.tx,rx.dequeued_at};read_={};
        if(config_refreshes_<max_time)++config_refreshes_;
        return;
    }
    const auto parsed=robot_core::mks::parse_response(f);if(!parsed.ok())return;
    const auto& p=parsed.parsed;
    if(p.code==0xFD){
        if(move_.id==0 || move_until_==0 || p.axis!=move_.axis || rx.dequeued_at<move_until_-2000)return;
        if(p.value==1){if(!started_){started_=true;status_.state=State::Moving;}}
        else if(p.value==2 && started_){if(!completed_){completed_=true;completed_at_=port_.now_ms();status_.state=State::Completing;for(auto& pr:proofs_)pr.positions_count=0;}}
        else {enter_stop(Fault::Command);return;}
        return;
    }
    const auto ci=code_index(p.code);
    if(ci<0 || !read_.active || read_.configuration || !read_.confirmed || p.axis!=profile_.gate.axes[read_.axis] || static_cast<unsigned>(ci)!=read_.code || rx.dequeued_at<read_.tx || rx.dequeued_at>=read_.deadline)return;
    auto& pr=proofs_[read_.axis];Sample sample{true,p.value,read_.tx,rx.dequeued_at};pr.sample[read_.code]=sample;
    if(ci==1){if(pr.positions_count<3)pr.positions[pr.positions_count++]=sample;else {pr.positions[0]=pr.positions[1];pr.positions[1]=pr.positions[2];pr.positions[2]=sample;}}
    read_={};
    if(ever_ready_ && ci==3 && p.value!=(expected_enabled(p.axis==profile_.gate.axes[0]?0:1)?1:0)){enter_stop(Fault::Observation);return;}
    if(ever_ready_ && ((ci==0 && p.value!=1) || (ci==2 && p.value!=0)) && (move_.id==0 || p.axis!=move_.axis)){enter_stop(Fault::Observation);return;}
    if(status_.state==State::Checking && proof()){status_.state=State::Ready;ever_ready_=true;publish(true);}
    else if(completed_ && proof(true)){
        const auto id=move_.id;status_.state=State::Ready;publish(true);
        if(!gate_.complete(port_.now_ms(),snapshot_,id)){enter_stop(Fault::Gate);return;}
        move_={};move_until_=start_until_=completed_at_=0;started_=completed_=false;
    } else if(ever_ready_)publish(status_.state==State::Ready && proof());
    sync_gate();
}
void BenchRun::schedule() noexcept {
    if(!deadlines()||inflight_||read_.active)return;
    robot_gate::Intent intent;
    if(gate_.take_intent(port_.now_ms(),snapshot_,intent)){
        if(intent.boot!=profile_.gate.boot || intent.revision!=snapshot_.revision || intent.pulses!=100 || intent.speed!=5 || intent.acceleration!=2 || intent.direction>1 || port_.now_ms()>=intent.dispatch_before){enter_stop(Fault::Gate);return;}
        move_=intent;const unsigned a=intent.axis==profile_.gate.axes[0]?0:1;baseline_=proofs_[a].sample[1].value;
        // Preserve current health samples, but discard all pre-movement position stability history.
        for(auto& p:proofs_)p.positions_count=0;
        status_.state=State::AwaitStart;move_until_=start_until_=0;started_=completed_=false;
        const auto f=robot_core::mks::build_move100(intent.axis,intent.direction==1);
        if(!f.ok()||!submit(f.frame,intent.dispatch_before,a,0,true)){if(active())enter_stop(Fault::Tx);return;}
        publish(false);sync_gate();return;
    }
    if(gate_.status().stopped_latched){sync_gate();return;}
    if(gate_.status().armed_axis!=0 && !gate_.status().dispatched)return;
    const auto now=port_.now_ms();if(now<next_read_)return;
    const unsigned total=static_cast<unsigned>(profile_.gate.count)*4;
    unsigned a=cursor_%profile_.gate.count,c=cursor_/profile_.gate.count;
    bool diagnostic_priority=false;Time oldest_diagnostic=max_time;
    if(boot_approved_)for(unsigned axis=0;axis<profile_.gate.count;++axis)for(unsigned index=0;index<4;++index){const auto& sample=proofs_[axis].sample[index];
        if(sample.valid && now>=sample.at && now-sample.at>=200 && sample.at<oldest_diagnostic){oldest_diagnostic=sample.at;a=axis;c=index;diagnostic_priority=true;}}
    unsigned config_axis=0,config_index=0;Time oldest_config=max_time;
    if(boot_approved_)for(unsigned axis=0;axis<profile_.gate.count;++axis)for(unsigned index=0;index<7;++index){const auto at=configurations_[axis][index].dequeued_at;if(at<oldest_config){oldest_config=at;config_axis=axis;config_index=index;}}
    const bool config_urgent=boot_approved_ && oldest_config<=max_time-4000 && oldest_config+4000-now<=600;
    const bool ordinary_config=boot_approved_ && config_slot_ && now>=oldest_config && now-oldest_config>=1000;
    if(!diagnostic_priority && (config_urgent || ordinary_config)){
        const auto previous=last_config_[config_axis][config_index];
        if(now>=previous && now-previous>=140){Time before;if(!add(now,50,before))return;
            const auto frame=robot_config::read_config(profile_.gate.axes[config_axis],robot_config::settings[config_index]);
            if(submit(frame.frame,before,config_axis,config_index,false,true)){config_slot_=false;add(now,20,next_read_);}return;}
    }
    if(last_read_[a][c]!=0 && (now<last_read_[a][c] || now-last_read_[a][c]<140))return;
    const auto f=robot_core::mks::build_read(profile_.gate.axes[a],codes[c]);Time before;
    if(!f.ok()||!add(now,50,before))return;
    if(submit(f.frame,before,a,c,false)){if(a==cursor_%profile_.gate.count && c==cursor_/profile_.gate.count){cursor_=(cursor_+1)%total;if(cursor_==0)config_slot_=true;}add(now,20,next_read_);}
}
void BenchRun::poll() noexcept {
    if(status_.state==State::Stopping){stop_poll(false);return;}
    if(!active())return;
    const auto now=port_.now_ms();operation_at_=now;
    if(now<last_poll_ || now-last_poll_>=10){enter_stop(Fault::Service);return;}last_poll_=now;
    if(!health())return;
    for(unsigned i=0;i<16;++i){RxFrame rx;const auto r=port_.receive(rx);if(r==ReceiveResult::Error){enter_stop(Fault::Rx);return;}if(!time_ok())return;if(r==ReceiveResult::Empty)break;if(!health())return;receive(rx);if(!active())return;}
    if(!health(true)||!deadlines())return;
    schedule();if(active())health();
}
robot_gate::Id BenchRun::open_session() noexcept { return open_session(0); }
robot_gate::Id BenchRun::open_session(Time who) noexcept {
    operation_at_=port_.now_ms();if(!active()||!deadlines() || (profile_.enable_policy==EnablePolicy::SingleSelected && who==0))return 0;const auto id=gate_.open_session(port_.now_ms(),snapshot_);if(id!=0)for(auto& item:principal_sessions_)if(item.session==0){item={id,who};break;}return id;
}
void BenchRun::close_session(robot_gate::Id id) noexcept {
    operation_at_=port_.now_ms();if(!active()||!deadlines())return;gate_.close_session(port_.now_ms(),snapshot_,id);for(auto& item:principal_sessions_)if(item.session==id)item={};sync_gate();
}
robot_gate::Result BenchRun::request(const robot_gate::Request& r) noexcept {
    operation_at_=port_.now_ms();if(!active()||!deadlines())return {robot_gate::Error::Stopping,0,0};
    if((r.op==robot_gate::Op::Arm || r.op==robot_gate::Op::Ticket) && !configuration_headroom(port_.now_ms(),400))return {robot_gate::Error::Busy,0,0};
    if((r.op==robot_gate::Op::Arm || r.op==robot_gate::Op::Ticket) && (read_.active||inflight_))return {robot_gate::Error::Busy,0,0};
    if(r.op==robot_gate::Op::Acquire && profile_.enable_policy==EnablePolicy::SingleSelected){bool owner=false;for(const auto& item:principal_sessions_)if(item.session==r.session && item.principal==principal_)owner=true;if(!owner)return {robot_gate::Error::Denied,0,0};}
    const auto result=gate_.handle(port_.now_ms(),snapshot_,r);if(r.op==robot_gate::Op::Acquire && result.error==robot_gate::Error::None)authority_until_=0;sync_gate();return result;
}
} // namespace robot_run
