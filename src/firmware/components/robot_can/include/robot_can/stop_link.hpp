#pragma once
#include "robot_can/can_port.hpp"
#include "robot_core/stop_coordinator.hpp"
#include <cstddef>

namespace robot_can {
enum class LinkState : std::uint8_t { Idle, Active, StoppedRecheck, Fault };
enum class LinkFault : std::uint8_t {
    None, Core, PortApi, Clock, ServiceGap, BusOff, RxLoss, BusFault,
    UnexpectedCompletion, Submit, RxBacklog, Cleanup, FinalizationTime
};
enum class EventKind : std::uint8_t { Isolation, Alerts, TxAccepted, Rx, Fault, Closed };
struct LogEvent {
    std::uint64_t at{0};
    EventKind kind{EventKind::Alerts};
    std::uint32_t detail{0};
    WireFrame frame{};
};

// One episode, one task, no I/O in construction. No motion/enable commands.
class StopLink {
public:
    explicit StopLink(CanPort& port) noexcept : port_(port) {}
    StopLink(const StopLink&) = delete;
    StopLink& operator=(const StopLink&) = delete;
    void begin_stop(const robot_core::StopProfile& profile) noexcept;
    void request_stop() noexcept;
    void poll() noexcept;
    LinkState state() const noexcept { return state_; }
    LinkFault fault() const noexcept { return fault_; }
    const robot_core::StopCoordinator& core() const noexcept { return core_; }
    CloseResult close_result() const noexcept { return closed_result_; }
    bool close_attempted() const noexcept { return closed_; }
    std::size_t log_size() const noexcept { return log_size_; }
    std::uint64_t overwritten_events() const noexcept { return overwritten_; }
    bool log_at(std::size_t oldest_index, LogEvent& out) const noexcept;
private:
    bool check_time() noexcept;
    bool check_health(bool require_empty_rx = false) noexcept;
    bool check_core() noexcept;
    void dispatch() noexcept;
    void fail(LinkFault why) noexcept;
    void finish(bool candidate_success) noexcept;
    void record(EventKind kind, std::uint32_t detail = 0, const WireFrame& frame = {}) noexcept;

    CanPort& port_;
    robot_core::StopCoordinator core_{};
    LinkState state_{LinkState::Idle};
    LinkFault fault_{LinkFault::None};
    std::uint64_t last_clock_{0}, last_poll_{0}, operation_start_{0};
    bool touched_{false}, closed_{false}, inflight_{false};
    std::uint32_t token_{0};
    CloseResult closed_result_{};
    std::array<LogEvent, 64> log_{};
    std::size_t log_head_{0}, log_size_{0};
    std::uint64_t overwritten_{0};
};
} // namespace robot_can
