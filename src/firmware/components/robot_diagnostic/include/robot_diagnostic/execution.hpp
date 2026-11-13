#pragma once
#include "robot_diagnostic/diagnostic.hpp"
#include <limits>
#include <string_view>

namespace robot_diagnostic {
enum class Board { Unknown=0, WaveshareCanU=1, Other=2, WaveshareCan=3 };
enum class Protocol { Unknown, MakerbaseCan, Rs485, Other };
enum class Check { Unknown, Pass, Fail };
enum class Readiness { Pending, Mismatch, ReadyForReview };
struct Observed {
    Board board{Board::Unknown};Protocol protocol{Protocol::Unknown};
    std::string_view hardware_revision{},firmware_version{};
    std::uint16_t can_id{0};std::uint32_t bitrate{0};
    int tx_gpio{-1},rx_gpio{-1};
    Check wiring{Check::Unknown},power_on_motion_excluded{Check::Unknown};
};
enum Issue : std::uint32_t { Selection=1u<<0, BoardIssue=1u<<1, ProtocolIssue=1u<<2,
    HardwareRecord=1u<<3,FirmwareRecord=1u<<4,IdIssue=1u<<5,RateIssue=1u<<6,
    PinIssue=1u<<7,WiringIssue=1u<<8,PowerOnIssue=1u<<9 };
struct PreparedProfile {
    Profile transport{};Readiness readiness{Readiness::Pending};
    std::uint32_t missing{0},mismatch{0};
};
// These are expected constraints, never observations or physical approval.
inline constexpr std::uint32_t expected_bitrate=500000;
inline constexpr int expected_tx=15,expected_rx=16;
inline Check record_quality(std::string_view s)noexcept {
    if(s.empty())return Check::Unknown;
    if(s.size()>64)return Check::Fail;
    bool visible=false;
    for(const unsigned char c:s){if(c<32 || c==127)return Check::Fail;if(c!=' ')visible=true;}
    return visible?Check::Pass:Check::Unknown;
}
inline PreparedProfile prepare_profile(const Observed& o,std::uint16_t selected)noexcept {
    PreparedProfile p{};p.transport.axis=selected;
    auto mark=[&](std::uint32_t bit,Check c){if(c==Check::Unknown)p.missing|=bit;else if(c!=Check::Pass)p.mismatch|=bit;};
    mark(Selection,selected==0?Check::Unknown:(selected==1||selected==2)?Check::Pass:Check::Fail);
    const bool supported_board=o.board==Board::WaveshareCanU||o.board==Board::WaveshareCan;
    mark(BoardIssue,o.board==Board::Unknown?Check::Unknown:supported_board?Check::Pass:Check::Fail);
    mark(ProtocolIssue,o.protocol==Protocol::Unknown?Check::Unknown:o.protocol==Protocol::MakerbaseCan?Check::Pass:Check::Fail);
    mark(HardwareRecord,record_quality(o.hardware_revision));mark(FirmwareRecord,record_quality(o.firmware_version));
    mark(IdIssue,o.can_id==0?Check::Unknown:o.can_id==selected?Check::Pass:Check::Fail);
    mark(RateIssue,o.bitrate==0?Check::Unknown:o.bitrate==expected_bitrate?Check::Pass:Check::Fail);
    const bool wrong_pin=(o.tx_gpio!=-1 && o.tx_gpio!=expected_tx)||(o.rx_gpio!=-1 && o.rx_gpio!=expected_rx);
    mark(PinIssue,wrong_pin?Check::Fail:o.tx_gpio==-1||o.rx_gpio==-1?Check::Unknown:Check::Pass);
    mark(WiringIssue,o.wiring);mark(PowerOnIssue,o.power_on_motion_excluded);
    p.readiness=p.mismatch?Readiness::Mismatch:p.missing?Readiness::Pending:Readiness::ReadyForReview;
    p.transport.board_confirmed=(p.missing&(BoardIssue|HardwareRecord|FirmwareRecord|PinIssue|WiringIssue))==0 && (p.mismatch&(BoardIssue|HardwareRecord|FirmwareRecord|PinIssue|WiringIssue))==0;
    p.transport.can_protocol_confirmed=o.protocol==Protocol::MakerbaseCan && record_quality(o.firmware_version)==Check::Pass;
    p.transport.bitrate_confirmed=o.bitrate==expected_bitrate;
    p.transport.no_power_on_motion_confirmed=o.power_on_motion_excluded==Check::Pass;
    p.transport.hardware_approved=false; // ReadyForReview cannot grant physical access.
    return p;
}
enum class Due { Early, Poll, ClockFault, LateFault, OverflowFault };
class Cadence {
public:
    bool begin(std::uint64_t now)noexcept {
        if(started_)return false;
        started_=true;last_observed_=last_service_=next_=now;
        if(now==std::numeric_limits<std::uint64_t>::max()){fault_=Due::OverflowFault;return false;}
        return true;
    }
    Due observe(std::uint64_t now)noexcept {
        if(!started_ || fault_!=Due::Early)return !started_?Due::ClockFault:fault_;
        if(now<last_observed_){fault_=Due::ClockFault;return fault_;}
        last_observed_=now;
        if(now-last_service_>=10){fault_=Due::LateFault;return fault_;}
        if(now<next_)return Due::Early;
        if(now==std::numeric_limits<std::uint64_t>::max()){fault_=Due::OverflowFault;return fault_;}
        last_service_=now;next_=now+1; // Skip missed slots; never catch up with a burst.
        return Due::Poll;
    }
    std::uint64_t next_due()const noexcept{return next_;}
private:
    bool started_{false};Due fault_{Due::Early};
    std::uint64_t last_observed_{0},last_service_{0},next_{0};
};
inline void service_scheduled_poll(Runner& runner,Cadence& cadence)noexcept {
    if(runner.terminal() || runner.state()==State::Idle)return;
    const auto due=cadence.observe(runner.schedule_now_ms());
    if(due==Due::Poll)runner.poll();
    else if(due!=Due::Early)runner.abort_schedule();
}
inline void schedule_wait_result(Runner& runner,bool blocked)noexcept {
    if(!runner.terminal() && runner.state()!=State::Idle && !blocked)runner.abort_schedule();
}
} // namespace robot_diagnostic
