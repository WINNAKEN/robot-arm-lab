#pragma once

#include "robot_core/mks_codec.hpp"
#include <array>
#include <cstddef>
#include <cstdint>

namespace robot_core {

enum class StopState : std::uint8_t {
    Idle, Isolating, StopCommands, Quiet, Verifying, StoppedRecheck, Fault
};
enum class StopFault : std::uint8_t {
    None, ProfileUnapproved, InvalidAxes, ClockReversed, TimeOverflow,
    OverallTimeout, IsolationTimeout, IsolationFailed, PreparationTimeout,
    VerificationTimeout, TxTimeout, ResponseTimeout, TxFailed, UnknownTxToken,
    UnexpectedEvent, ActionNotConsumed, SlotMissed, TxOverlap, RequeryTooSoon,
    ReceiveDelay, ReceiveOverflow, BusOff, StopRejected, Moving, UnstablePosition,
    StaleObservation, TransportFailure
};
struct StopProfile {
    std::array<std::uint16_t, 2> axes{1, 2};
    std::uint8_t axis_count{2};
    bool heartbeat_1000_readback_confirmed{false};
    bool response_bounds_approved{false};
    bool position_tolerance_approved{false};
    std::uint64_t tolerance_counts{0};
};
struct StopAction {
    enum class Kind : std::uint8_t { Isolate, Transmit };
    Kind kind{Kind::Isolate};
    std::uint32_t token{0}; // Local TX-completion correlation; never sent on CAN.
    mks::Frame frame{};
    std::uint64_t dispatch_before{0}; // Adapter must submit before this time too.
};

// Single-owner, nonblocking core. The caller serializes every input and drains
// actions promptly. No hardware, allocation, network, or clock APIs are used.
class StopCoordinator {
public:
    void begin(std::uint64_t now, const StopProfile& profile) noexcept;
    void request_stop(std::uint64_t now) noexcept;
    void tick(std::uint64_t now) noexcept;
    void on_isolated(std::uint64_t now, bool success) noexcept;
    void on_tx_result(std::uint64_t now, std::uint32_t token, bool success) noexcept;
    void on_frame(std::uint64_t now, std::uint64_t dequeued_at,
                  const mks::Frame& frame) noexcept;
    void on_bus_off(std::uint64_t now) noexcept;
    void on_receive_overflow(std::uint64_t now) noexcept;
    void on_transport_error(std::uint64_t now) noexcept;
    bool take_action(std::uint64_t now, StopAction& out) noexcept;

    StopState state() const noexcept { return state_; }
    StopFault fault() const noexcept { return fault_; }
    std::uint64_t started_at() const noexcept { return started_at_; }
    std::uint64_t deadline() const noexcept { return overall_deadline_; }
    std::uint64_t verification_start() const noexcept { return verify_start_; }
    std::uint8_t issued_stop_count() const noexcept { return issued_stops_; }

private:
    struct Pending {
        bool active{false};
        bool sent_before{false};
        std::uint64_t tx_at{0};
        std::uint64_t deadline{0};
        std::uint8_t cycle{0};
    };
    struct AxisProof {
        std::array<std::int64_t, 3> positions{};
        std::array<bool, 3> position_seen{};
        std::array<bool, 4> latest_seen{};
        std::array<std::uint64_t, 4> latest_at{};
    };
    bool active() const noexcept;
    bool advance(std::uint64_t now) noexcept;
    void fail(StopFault fault) noexcept;
    void send(std::uint64_t now, const mks::Frame& frame,
              std::uint8_t pending_index, std::uint8_t cycle) noexcept;
    void send_next_stop(std::uint64_t now) noexcept;
    void consider_complete(std::uint64_t now) noexcept;
    int axis_index(std::uint16_t id) const noexcept;
    static int code_index(std::uint8_t code) noexcept;

    StopState state_{StopState::Idle};
    StopFault fault_{StopFault::None};
    StopProfile profile_{};
    std::uint64_t last_now_{0}, started_at_{0}, overall_deadline_{0};
    std::uint64_t isolation_deadline_{0}, preparation_deadline_{0};
    std::uint64_t quiet_until_{0}, verify_start_{0}, verify_deadline_{0};
    std::uint64_t tx_deadline_{0}, ack_deadline_{0}, last_tx_{0};
    StopAction action_{};
    bool action_ready_{false}, inflight_{false}, stop_ack_pending_{false};
    std::uint32_t next_token_{1}, inflight_token_{0};
    std::uint8_t tx_pending_index_{0}, tx_cycle_{0};
    std::uint8_t stop_axis_{0}, issued_stops_{0}, next_slot_{0};
    std::array<Pending, 8> pending_{};
    std::array<AxisProof, 2> proof_{};
};

} // namespace robot_core
