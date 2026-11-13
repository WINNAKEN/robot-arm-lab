#include "robot_core/stop_coordinator.hpp"
#include <limits>

namespace robot_core {
namespace {
constexpr std::array<std::uint8_t, 4> codes{0x31, 0xF1, 0x32, 0x3A};
constexpr std::uint64_t max_position_range = (std::uint64_t{1} << 48) - 1;
}

bool StopCoordinator::active() const noexcept {
    return state_ != StopState::Idle && state_ != StopState::Fault &&
           state_ != StopState::StoppedRecheck;
}

void StopCoordinator::fail(StopFault fault) noexcept {
    state_ = StopState::Fault;
    fault_ = fault;
    action_ready_ = false;
    inflight_ = false;
    stop_ack_pending_ = false;
    for (auto& p : pending_) p.active = false;
}

void StopCoordinator::begin(std::uint64_t now, const StopProfile& profile) noexcept {
    if (state_ != StopState::Idle) { request_stop(now); return; }
    profile_ = profile;
    last_now_ = started_at_ = now;
    if (now > std::numeric_limits<std::uint64_t>::max() - 3600) {
        fail(StopFault::TimeOverflow); return;
    }
    overall_deadline_ = now + 3600;
    isolation_deadline_ = now + 100;
    preparation_deadline_ = now + 600;
    const bool axes_ok = (profile.axis_count == 1 &&
        (profile.axes[0] == 1 || profile.axes[0] == 2)) ||
        (profile.axis_count == 2 && profile.axes[0] == 1 && profile.axes[1] == 2);
    if (!axes_ok) { fail(StopFault::InvalidAxes); return; }
    if (!profile.heartbeat_1000_readback_confirmed || !profile.response_bounds_approved ||
        !profile.position_tolerance_approved || profile.tolerance_counts > max_position_range) {
        fail(StopFault::ProfileUnapproved); return;
    }
    state_ = StopState::Isolating;
    action_ = StopAction{};
    action_.dispatch_before = isolation_deadline_;
    action_ready_ = true;
}

bool StopCoordinator::advance(std::uint64_t now) noexcept {
    if (!active()) return false;
    if (now < last_now_) { fail(StopFault::ClockReversed); return false; }
    last_now_ = now;
    if (now >= overall_deadline_) { fail(StopFault::OverallTimeout); return false; }
    if (state_ == StopState::Isolating && now >= isolation_deadline_) {
        fail(StopFault::IsolationTimeout); return false;
    }
    if (state_ == StopState::StopCommands && now >= preparation_deadline_) {
        fail(StopFault::PreparationTimeout); return false;
    }
    if (state_ == StopState::Verifying && now >= verify_deadline_) {
        fail(StopFault::VerificationTimeout); return false;
    }
    if (inflight_ && now >= tx_deadline_) { fail(StopFault::TxTimeout); return false; }
    if (stop_ack_pending_ && now >= ack_deadline_) {
        fail(StopFault::ResponseTimeout); return false;
    }
    for (const auto& p : pending_) {
        if (p.active && now >= p.deadline) { fail(StopFault::ResponseTimeout); return false; }
    }
    return true;
}

bool StopCoordinator::take_action(std::uint64_t now, StopAction& out) noexcept {
    if (!advance(now)) return false;
    if (!action_ready_) return false;
    if (now >= action_.dispatch_before) {
        fail(StopFault::SlotMissed); return false;
    }
    out = action_;
    action_ready_ = false;
    return true;
}

void StopCoordinator::request_stop(std::uint64_t now) noexcept {
    // Never reset deadlines, counters, or terminal state.
    (void)advance(now);
}

void StopCoordinator::send(std::uint64_t now, const mks::Frame& frame,
                           std::uint8_t pending_index, std::uint8_t cycle) noexcept {
    if (action_ready_) { fail(StopFault::ActionNotConsumed); return; }
    if (inflight_) { fail(StopFault::TxOverlap); return; }
    if (now > std::numeric_limits<std::uint64_t>::max() - 50) {
        fail(StopFault::TimeOverflow); return;
    }
    action_ = {StopAction::Kind::Transmit, next_token_++, frame};
    action_ready_ = true;
    inflight_ = true;
    inflight_token_ = action_.token;
    tx_deadline_ = now + 50;
    action_.dispatch_before = state_ == StopState::Verifying
        ? verify_start_ + static_cast<std::uint64_t>(next_slot_) * 60 + 10
        : tx_deadline_;
    tx_pending_index_ = pending_index;
    tx_cycle_ = cycle;
}

void StopCoordinator::send_next_stop(std::uint64_t now) noexcept {
    const auto encoded = mks::build_stop(profile_.axes[stop_axis_]);
    if (!encoded.ok()) { fail(StopFault::UnexpectedEvent); return; }
    send(now, encoded.frame, 0, 0);
    if (active()) ++issued_stops_;
}

void StopCoordinator::on_isolated(std::uint64_t now, bool success) noexcept {
    if (!advance(now)) return;
    if (state_ != StopState::Isolating) { fail(StopFault::UnexpectedEvent); return; }
    if (action_ready_) { fail(StopFault::ActionNotConsumed); return; }
    if (!success) { fail(StopFault::IsolationFailed); return; }
    state_ = StopState::StopCommands;
    send_next_stop(now);
}

void StopCoordinator::on_tx_result(std::uint64_t now, std::uint32_t token,
                                  bool success) noexcept {
    if (!advance(now)) return;
    if (!inflight_ || token != inflight_token_) { fail(StopFault::UnknownTxToken); return; }
    if (action_ready_) { fail(StopFault::ActionNotConsumed); return; }
    if (!success) { fail(StopFault::TxFailed); return; }
    inflight_ = false;
    last_tx_ = now;
    if (state_ == StopState::StopCommands) {
        // Future quiet+verification end is checked before adding either interval.
        if (now > std::numeric_limits<std::uint64_t>::max() - 3000) {
            fail(StopFault::TimeOverflow); return;
        }
        stop_ack_pending_ = true;
        ack_deadline_ = now + 200;
    } else if (state_ == StopState::Verifying) {
        auto& p = pending_[tx_pending_index_];
        p.active = p.sent_before = true;
        p.tx_at = now;
        p.deadline = now + 110; // Safe: verification deadline was overflow checked.
        p.cycle = tx_cycle_;
    } else {
        fail(StopFault::UnexpectedEvent);
    }
}

int StopCoordinator::axis_index(std::uint16_t id) const noexcept {
    for (std::uint8_t i = 0; i < profile_.axis_count; ++i)
        if (profile_.axes[i] == id) return i;
    return -1;
}
int StopCoordinator::code_index(std::uint8_t code) noexcept {
    for (std::size_t i = 0; i < codes.size(); ++i)
        if (codes[i] == code) return static_cast<int>(i);
    return -1;
}

void StopCoordinator::tick(std::uint64_t now) noexcept {
    if (!advance(now)) return;
    if (state_ == StopState::Quiet && now >= quiet_until_) {
        state_ = StopState::Verifying;
        // Use the fixed end of Quiet, never the delayed tick arrival time.
        verify_start_ = quiet_until_;
        verify_deadline_ = verify_start_ + 1700;
        if (now >= verify_deadline_) { fail(StopFault::VerificationTimeout); return; }
    }
    if (state_ != StopState::Verifying) return;
    const auto cycle_slots = static_cast<std::uint8_t>(4 * profile_.axis_count);
    if (next_slot_ >= 3 * cycle_slots) { consider_complete(now); return; }
    const auto slot_at = verify_start_ + static_cast<std::uint64_t>(next_slot_) * 60;
    if (now < slot_at) return;
    if (now - slot_at >= 10) { fail(StopFault::SlotMissed); return; }
    const auto within = static_cast<std::uint8_t>(next_slot_ % cycle_slots);
    const auto ax = static_cast<std::uint8_t>(within % profile_.axis_count);
    const auto code = static_cast<std::uint8_t>(within / profile_.axis_count);
    const auto index = static_cast<std::uint8_t>(ax * 4 + code);
    const auto& previous = pending_[index];
    if (previous.active || (previous.sent_before && now - previous.tx_at <= 130)) {
        fail(StopFault::RequeryTooSoon); return;
    }
    const auto encoded = mks::build_read(profile_.axes[ax], codes[code]);
    if (!encoded.ok()) { fail(StopFault::UnexpectedEvent); return; }
    send(now, encoded.frame, index, static_cast<std::uint8_t>(next_slot_ / cycle_slots));
    if (active()) ++next_slot_;
}

void StopCoordinator::on_frame(std::uint64_t now, std::uint64_t dequeued_at,
                              const mks::Frame& frame) noexcept {
    if (!advance(now)) return;
    if (dequeued_at > now || now - dequeued_at >= 10) {
        fail(StopFault::ReceiveDelay); return;
    }
    const auto result = mks::parse_response(frame);
    if (!result.ok()) return;
    const auto& rx = result.parsed;
    if (state_ == StopState::StopCommands && stop_ack_pending_ &&
        rx.axis == profile_.axes[stop_axis_] && rx.code == 0xF7) {
        if (dequeued_at < last_tx_) return;
        if (rx.value != 1) { fail(StopFault::StopRejected); return; }
        stop_ack_pending_ = false;
        if (++stop_axis_ < profile_.axis_count) send_next_stop(now);
        else { state_ = StopState::Quiet; quiet_until_ = last_tx_ + 1300; }
        return;
    }
    if (state_ != StopState::Verifying) return;
    const int ax = axis_index(rx.axis);
    const int ci = code_index(rx.code);
    if (ax < 0 || ci < 0) return;
    auto& p = pending_[static_cast<std::size_t>(ax * 4 + ci)];
    if (!p.active || dequeued_at < p.tx_at || dequeued_at >= p.deadline) return;
    p.active = false;
    auto& proof = proof_[static_cast<std::size_t>(ax)];
    if ((rx.code == 0xF1 && rx.value != 1) || (rx.code == 0x32 && rx.value != 0)) {
        fail(StopFault::Moving); return;
    }
    if (rx.code == 0x31) {
        proof.positions[p.cycle] = rx.value;
        proof.position_seen[p.cycle] = true;
    }
    if (p.cycle == 2) {
        proof.latest_seen[static_cast<std::size_t>(ci)] = true;
        proof.latest_at[static_cast<std::size_t>(ci)] = dequeued_at;
    }
    consider_complete(now);
}

void StopCoordinator::consider_complete(std::uint64_t now) noexcept {
    if (state_ != StopState::Verifying || next_slot_ != 12 * profile_.axis_count ||
        inflight_ || action_ready_) return;
    for (const auto& p : pending_) if (p.active) return;
    for (std::uint8_t a = 0; a < profile_.axis_count; ++a) {
        const auto& proof = proof_[a];
        auto min = proof.positions[0], max = min;
        for (std::size_t i = 0; i < 3; ++i) {
            if (!proof.position_seen[i]) return;
            if (proof.positions[i] < min) min = proof.positions[i];
            if (proof.positions[i] > max) max = proof.positions[i];
        }
        if (static_cast<std::uint64_t>(max - min) > profile_.tolerance_counts) {
            fail(StopFault::UnstablePosition); return;
        }
        for (std::size_t i = 0; i < 4; ++i) {
            if (!proof.latest_seen[i]) return;
            if (now - proof.latest_at[i] >= 700) {
                fail(StopFault::StaleObservation); return;
            }
        }
    }
    state_ = StopState::StoppedRecheck;
}

void StopCoordinator::on_bus_off(std::uint64_t now) noexcept {
    if (advance(now)) fail(StopFault::BusOff);
}
void StopCoordinator::on_receive_overflow(std::uint64_t now) noexcept {
    if (advance(now)) fail(StopFault::ReceiveOverflow);
}
void StopCoordinator::on_transport_error(std::uint64_t now) noexcept {
    if (advance(now)) fail(StopFault::TransportFailure);
}

} // namespace robot_core
