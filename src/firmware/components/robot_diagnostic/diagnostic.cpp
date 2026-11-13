#include "robot_diagnostic/diagnostic.hpp"
#include "robot_core/mks_codec.hpp"
#include <limits>

namespace robot_diagnostic {
namespace {
constexpr std::array<std::uint8_t,4> codes{{0x3A,0xF1,0x31,0x32}};
}
bool is_read_request(const robot_can::WireFrame& f,std::uint16_t axis) noexcept {
    if ((axis!=1 && axis!=2) || f.id!=axis || f.extended || f.rtr || f.dlc!=2) return false;
    const auto code=f.data[0];
    if (code!=0x3A && code!=0xF1 && code!=0x31 && code!=0x32) return false;
    if (f.data[1]!=static_cast<std::uint8_t>((axis+code)&0xFFu)) return false;
    for (std::size_t i=2;i<f.data.size();++i) if (f.data[i]!=0) return false;
    return true;
}
bool Runner::terminal()const noexcept {
    return state_==State::Complete || state_==State::Fault || state_==State::Rejected;
}
void Runner::abort_schedule()noexcept {
    if(state_!=State::Idle && !terminal())fail(Error::Schedule);
}
bool Runner::emit(Kind kind,const robot_can::WireFrame& frame,std::uint64_t dequeued,std::int64_t value)noexcept {
    if (count_>=profile_.record_limit || count_>=events_.size()) {
        overflow_=true;
        if (error_==Error::None) error_=Error::JournalFull;
        return false;
    }
    events_[count_++]={kind,last_,dequeued,frame,value,error_};return true;
}
void Runner::finish(bool successful)noexcept {
    if (attempted_ && !closed_) {
        closed_=true;closed_result_=port_.close();const auto now=port_.now_ms();
        if (error_==Error::None) {
            if (now<last_) error_=Error::Clock;
            else if (now-start_>=total_ms) error_=Error::Timeout;
            else if (polling_ && now-poll_start_>=10) error_=Error::Service;
            else if (!closed_result_.quiesced || !closed_result_.healthy) error_=Error::Close;
        }
        last_=now;
        if (!emit(Kind::Close)) successful=false;
    }
    state_=successful && error_==Error::None ? State::Complete : State::Fault;
}
void Runner::fail(Error reason)noexcept {
    if (terminal()) return;
    if (error_==Error::None) error_=reason;
    (void)emit(Kind::Failure);finish(false);
}
bool Runner::time_ok()noexcept {
    const auto now=port_.now_ms();
    if (now<last_) { fail(Error::Clock);return false; }
    last_=now;
    if (now-start_>=total_ms) { fail(Error::Timeout);return false; }
    if (polling_ && now-poll_start_>=10) { fail(Error::Service);return false; }
    if ((state_==State::AwaitTx && now-submitted_>=tx_ms) ||
        (state_==State::AwaitRx && now-submitted_>=response_ms)) { fail(Error::Timeout);return false; }
    return true;
}
bool Runner::health()noexcept {
    std::uint32_t alerts=0;
    if (!port_.read_alerts(alerts)) { fail(Error::Port);return false; }
    last_alerts_=alerts;
    if (!time_ok()) return false;
    if ((alerts & ~robot_can::all_alerts)!=0 || (alerts & (robot_can::fatal_alerts|robot_can::TxFailed))!=0) { fail(Error::Alert);return false; }
    if ((alerts & robot_can::TxSuccess)!=0) {
        if (state_!=State::AwaitTx) { fail(Error::Alert);return false; }
        state_=State::AwaitRx;
        if (!emit(Kind::TxComplete)) { fail(Error::JournalFull);return false; }
    }
    if (!port_.status(status_)) { fail(Error::Port);return false; }
    if (!time_ok()) return false;
    if (status_.state!=robot_can::BusState::Running || !robot_can::error_counters_clear(status_) ||
        status_.tx_pending>(state_==State::AwaitTx?1u:0u) || status_.rx_pending>16) { fail(Error::Busy);return false; }
    return true;
}
bool Runner::begin(const Profile& p)noexcept {
    if (used_) return false;
    used_=true;profile_=p;
    if ((p.axis!=1 && p.axis!=2) || !p.board_confirmed || !p.can_protocol_confirmed ||
        !p.bitrate_confirmed || !p.no_power_on_motion_confirmed || !p.hardware_approved ||
        p.record_limit==0 || p.record_limit>events_.size()) { error_=Error::Profile;state_=State::Rejected;return false; }
    start_=last_=last_poll_=port_.now_ms();
    if (start_>std::numeric_limits<std::uint64_t>::max()-total_ms) { error_=Error::Clock;state_=State::Rejected;return false; }
    if (!emit(Kind::Begin)) { fail(Error::JournalFull);return false; }
    attempted_=true;
    if (!port_.reset_and_start()) { fail(Error::Port);return false; }
    last_=port_.now_ms();
    if (last_<start_) { fail(Error::Clock);return false; }
    if (last_-start_>=100) { fail(Error::Timeout);return false; }
    state_=State::Gap;
    std::uint32_t alerts=0;
    if (!port_.read_alerts(alerts)) { fail(Error::Port);return false; }
    last_alerts_=alerts;
    if (!port_.status(status_)) { fail(Error::Port);return false; }
    if (!time_ok()) return false;
    if (last_-start_>=100) { fail(Error::Timeout);return false; }
    if (alerts!=0 || status_.state!=robot_can::BusState::Running || !robot_can::error_counters_clear(status_) || status_.tx_pending || status_.rx_pending) { fail(Error::Busy);return false; }
    gap_start_=last_;last_poll_=last_;
    return true;
}
void Runner::send()noexcept {
    const auto encoded=robot_core::mks::build_read(profile_.axis,codes[index_]);
    robot_can::WireFrame frame{encoded.frame.id,encoded.frame.dlc,encoded.frame.data,encoded.frame.extended,encoded.frame.rtr};
    if (!encoded.ok() || !is_read_request(frame,profile_.axis)) { fail(Error::Request);return; }
    if (!time_ok()) return;
    submitted_=last_;
    if (submitted_>std::numeric_limits<std::uint64_t>::max()-10) { fail(Error::Clock);return; }
    if (!emit(Kind::Submit,frame)) { fail(Error::JournalFull);return; }
    const bool accepted=port_.submit(frame,submitted_+10);
    state_=State::AwaitTx;
    if (!time_ok()) return;
    if (!accepted) { fail(Error::Port);return; }
    if (!emit(Kind::Accepted,frame)) fail(Error::JournalFull);
}
void Runner::poll()noexcept {
    if (state_==State::Idle || terminal()) return;
    const auto now=port_.now_ms();
    if (now<last_) { fail(Error::Clock);return; }
    if (now-last_poll_>=10) { fail(Error::Service);return; }
    last_poll_=poll_start_=now;polling_=true;
    if (!time_ok() || !health()) { polling_=false;return; }
    bool matched=false;
    for (unsigned i=0;i<2;++i) {
        if (count_>=profile_.record_limit) { fail(Error::JournalFull);break; }
        robot_can::RxFrame rx{};const auto previous=last_;const auto result=port_.receive(rx);last_=port_.now_ms();
        if (result==robot_can::ReceiveResult::Data && !emit(Kind::RxRaw,rx.frame,rx.dequeued_at)) { fail(Error::JournalFull);break; }
        if (last_<previous) { fail(Error::Clock);break; }
        if (!time_ok()) break;
        if (result==robot_can::ReceiveResult::Error) { fail(Error::Port);break; }
        if (result==robot_can::ReceiveResult::Empty) break;
        if (matched || state_!=State::AwaitRx) { fail(Error::UnexpectedRx);break; }
        if (rx.dequeued_at==0 || rx.dequeued_at<submitted_ || rx.dequeued_at>last_) { fail(Error::Frame);break; }
        if (rx.frame.id!=profile_.axis || rx.frame.extended || rx.frame.rtr || rx.frame.dlc>8) { fail(Error::Frame);break; }
        robot_core::mks::Frame frame{static_cast<std::uint16_t>(rx.frame.id),rx.frame.dlc,rx.frame.data,rx.frame.extended,rx.frame.rtr};
        const auto parsed=robot_core::mks::parse_response(frame);
        if (!parsed.ok() || parsed.parsed.code!=codes[index_]) { fail(Error::Frame);break; }
        const auto value=parsed.parsed.value;values_[index_]=value;seen_[index_]=true;
        if (!emit(Kind::Value,rx.frame,rx.dequeued_at,value)) { fail(Error::JournalFull);break; }
        if ((index_==0 && value!=0) || (index_==1 && value!=1)) { fail(Error::Device);break; }
        matched=true;
    }
    if (!terminal() && health()) {
        if (status_.rx_pending) fail(Error::Busy);
        else if (matched) {
            ++index_;
            if (index_==codes.size()) finish(true);
            else {state_=State::Gap;gap_start_=last_;}
        } else if (state_==State::Gap && (index_==0 || last_-gap_start_>=gap_ms)) send();
    }
    polling_=false;
}
} // namespace robot_diagnostic
