#pragma once
#include "robot_can/can_port.hpp"
#include <array>
#include <cstddef>
#include <cstdint>

namespace robot_diagnostic {
enum class State { Idle, Gap, AwaitTx, AwaitRx, Complete, Fault, Rejected };
enum class Error { None, Profile, Clock, Service, Timeout, Port, Busy, Alert,
                   Frame, UnexpectedRx, Device, JournalFull, Close, Request, Schedule };
enum class Kind { Begin, Submit, Accepted, TxComplete, RxRaw, Value, Failure, Close };
struct Profile {
    std::uint16_t axis{0};
    bool board_confirmed{false}, can_protocol_confirmed{false};
    bool bitrate_confirmed{false}, no_power_on_motion_confirmed{false};
    bool hardware_approved{false};
    std::size_t record_limit{128}; // May be lowered for bounded HOST fault injection.
};
struct Event {
    Kind kind{};
    std::uint64_t at{0}, dequeued_at{0};
    robot_can::WireFrame frame{};
    std::int64_t value{0};
    Error error{Error::None};
};
// Inspect the actual outgoing frame immediately before the only submit call.
bool is_read_request(const robot_can::WireFrame&, std::uint16_t axis) noexcept;
class Runner final {
public:
    explicit Runner(robot_can::CanPort& port) noexcept : port_(port) {}
    Runner(const Runner&)=delete;
    Runner& operator=(const Runner&)=delete;
    bool begin(const Profile&) noexcept;
    void poll() noexcept;
    void abort_schedule() noexcept;
    std::uint64_t schedule_now_ms()const noexcept { return terminal()||state_==State::Idle?0:port_.now_ms(); }
    State state() const noexcept { return state_; }
    Error error() const noexcept { return error_; }
    bool terminal() const noexcept;
    std::size_t event_count() const noexcept { return count_; }
    const Event& event(std::size_t index) const noexcept { return events_[index]; }
    bool journal_overflow() const noexcept { return overflow_; }
    const std::array<std::int64_t,4>& values() const noexcept { return values_; }
    const std::array<bool,4>& values_seen() const noexcept { return seen_; }
    robot_can::CloseResult close_result() const noexcept { return closed_result_; }
    robot_can::PortStatus last_status() const noexcept { return status_; }
    std::uint32_t last_alerts() const noexcept { return last_alerts_; }
    static constexpr std::uint64_t tx_ms=250, response_ms=500, gap_ms=150, total_ms=4000;
private:
    bool time_ok() noexcept;
    bool health() noexcept;
    bool emit(Kind, const robot_can::WireFrame& = {}, std::uint64_t dequeued=0, std::int64_t value=0) noexcept;
    void fail(Error) noexcept;
    void finish(bool successful) noexcept;
    void send() noexcept;
    robot_can::CanPort& port_;
    State state_{State::Idle}; Error error_{Error::None};
    Profile profile_{};
    bool used_{false}, attempted_{false}, closed_{false}, polling_{false}, overflow_{false};
    std::uint64_t start_{0}, last_{0}, last_poll_{0}, poll_start_{0}, submitted_{0}, gap_start_{0};
    std::size_t index_{0}, count_{0};
    std::array<Event,128> events_{};
    std::array<std::int64_t,4> values_{};
    std::array<bool,4> seen_{};
    robot_can::PortStatus status_{};
    std::uint32_t last_alerts_{0};
    robot_can::CloseResult closed_result_{};
};
} // namespace robot_diagnostic
