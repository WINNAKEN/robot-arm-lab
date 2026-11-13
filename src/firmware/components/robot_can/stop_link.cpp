#include "robot_can/stop_link.hpp"
#include <limits>

namespace robot_can {
using robot_core::StopState;

void StopLink::record(EventKind kind, std::uint32_t detail, const WireFrame& frame) noexcept {
    log_[log_head_] = {port_.now_ms(), kind, detail, frame};
    log_head_ = (log_head_ + 1) % log_.size();
    if (log_size_ < log_.size()) ++log_size_;
    else if (overwritten_ < std::numeric_limits<std::uint64_t>::max()) ++overwritten_;
}
bool StopLink::log_at(std::size_t index, LogEvent& out) const noexcept {
    if (index >= log_size_) return false;
    out = log_[(log_head_ + log_.size() - log_size_ + index) % log_.size()];
    return true;
}

void StopLink::finish(bool candidate_success) noexcept {
    if (closed_) return;
    if (touched_) {
        closed_ = true;
        closed_result_ = port_.close();
        record(EventKind::Closed, (closed_result_.quiesced ? 1u : 0u) |
                                  (closed_result_.healthy ? 2u : 0u));
    }
    if (!candidate_success) return;
    const auto now = port_.now_ms();
    // The core is already terminal. Its advance() intentionally does not run here.
    if (now < last_clock_ || now < operation_start_ || now - operation_start_ >= 10 ||
        now >= core_.deadline() || now >= core_.verification_start() + 1700) {
        state_ = LinkState::Fault;
        fault_ = LinkFault::FinalizationTime;
    } else if (!closed_ || !closed_result_.quiesced || !closed_result_.healthy) {
        state_ = LinkState::Fault;
        fault_ = LinkFault::Cleanup;
    } else {
        state_ = LinkState::StoppedRecheck;
    }
    if (state_ == LinkState::Fault) record(EventKind::Fault, static_cast<std::uint32_t>(fault_));
}
void StopLink::fail(LinkFault why) noexcept {
    if (state_ != LinkState::Active) return;
    state_ = LinkState::Fault;
    fault_ = why;
    const auto now = port_.now_ms();
    if (why == LinkFault::BusOff) core_.on_bus_off(now);
    else if (why == LinkFault::RxLoss || why == LinkFault::RxBacklog) core_.on_receive_overflow(now);
    else if (why != LinkFault::Core) core_.on_transport_error(now);
    inflight_ = false;
    record(EventKind::Fault, static_cast<std::uint32_t>(why));
    finish(false);
}
bool StopLink::check_core() noexcept {
    if (core_.state() == StopState::Fault) fail(LinkFault::Core);
    return state_ == LinkState::Active;
}
bool StopLink::check_time() noexcept {
    const auto now = port_.now_ms();
    if (now < last_clock_) { fail(LinkFault::Clock); return false; }
    if (now - operation_start_ >= 10) { fail(LinkFault::ServiceGap); return false; }
    last_clock_ = now;
    // Expire first without creating another action while the current one is pending.
    core_.request_stop(now);
    return check_core();
}

bool StopLink::check_health(bool require_empty_rx) noexcept {
    std::uint32_t alerts = 0;
    PortStatus status;
    if (!port_.read_alerts(alerts)) { fail(LinkFault::PortApi); return false; }
    if (alerts != 0) record(EventKind::Alerts, alerts);
    if (!port_.status(status)) { fail(LinkFault::PortApi); return false; }
    if (!check_time()) return false;
    // Error evidence wins over a coalesced completion in the same batch.
    if ((alerts & BusOff) || status.state == BusState::BusOff || status.state == BusState::Recovering) {
        fail(LinkFault::BusOff); return false;
    }
    if ((alerts & (RxQueueFull | RxFifoOverrun)) || status.rx_missed || status.rx_overrun) {
        fail(LinkFault::RxLoss); return false;
    }
    if ((alerts & fatal_alerts) || (alerts & ~all_alerts) || !error_counters_clear(status)) {
        fail(LinkFault::BusFault); return false;
    }
    if (status.state != BusState::Running) { fail(LinkFault::PortApi); return false; }
    if (status.rx_pending > 16 || (require_empty_rx && status.rx_pending != 0)) {
        fail(LinkFault::RxBacklog); return false;
    }
    if (status.tx_pending > 1 || (status.tx_pending != 0 && !inflight_)) {
        fail(LinkFault::UnexpectedCompletion); return false;
    }
    const auto terminal = alerts & (TxSuccess | TxFailed);
    if (terminal != 0) {
        if (!inflight_ || status.tx_pending != 0 || terminal == (TxSuccess | TxFailed)) {
            fail(LinkFault::UnexpectedCompletion); return false;
        }
        inflight_ = false;
        core_.on_tx_result(port_.now_ms(), token_, terminal == TxSuccess);
        if (!check_core()) return false;
    }
    // TxIdle alone, and ESP_OK with an empty alert set, are not completions.
    return true;
}

void StopLink::begin_stop(const robot_core::StopProfile& profile) noexcept {
    if (state_ != LinkState::Idle) { request_stop(); return; }
    last_clock_ = last_poll_ = operation_start_ = port_.now_ms();
    state_ = LinkState::Active;
    core_.begin(last_clock_, profile);
    if (!check_core()) return; // No driver API for an unapproved profile.
    robot_core::StopAction isolate;
    if (!core_.take_action(port_.now_ms(), isolate) ||
        isolate.kind != robot_core::StopAction::Kind::Isolate) {
        if (check_core()) fail(LinkFault::PortApi);
        return;
    }
    touched_ = true;
    const bool ready = port_.reset_and_start();
    const auto now = port_.now_ms();
    core_.on_isolated(now, ready); // 100ms isolation bound includes the API call.
    record(EventKind::Isolation, ready ? 1u : 0u);
    if (!check_core()) return;
    last_clock_ = last_poll_ = operation_start_ = now;
    dispatch();
}
void StopLink::request_stop() noexcept {
    if (state_ != LinkState::Active) return;
    core_.request_stop(port_.now_ms());
    if (check_core()) poll();
}
void StopLink::dispatch() noexcept {
    if (!check_time() || !check_health()) return;
    robot_core::StopAction action;
    if (!core_.take_action(port_.now_ms(), action)) { (void)check_core(); return; }
    if (action.kind != robot_core::StopAction::Kind::Transmit || inflight_) {
        fail(LinkFault::UnexpectedCompletion); return;
    }
    // Never create a new response window while an already queued RX is known.
    // No hardware timestamp exists to date a frame arriving after this check.
    if (!check_health(true) || !check_time()) return;
    if (port_.now_ms() >= action.dispatch_before) { fail(LinkFault::Submit); return; }
    WireFrame frame{action.frame.id, action.frame.dlc, action.frame.data,
                    action.frame.extended, action.frame.rtr};
    token_ = action.token;
    inflight_ = true;
    if (!port_.submit(frame, action.dispatch_before)) { fail(LinkFault::Submit); return; }
    record(EventKind::TxAccepted, token_, frame);
    if (!check_time()) return;
    if (port_.now_ms() >= action.dispatch_before) fail(LinkFault::Submit);
}
void StopLink::poll() noexcept {
    if (state_ != LinkState::Active) return;
    const auto now = port_.now_ms();
    if (now < last_clock_ || now < last_poll_) { fail(LinkFault::Clock); return; }
    if (now - last_poll_ >= 10) { fail(LinkFault::ServiceGap); return; }
    last_poll_ = operation_start_ = now;
    if (!check_time() || !check_health()) return;

    for (unsigned i = 0; i < 16; ++i) {
        RxFrame rx;
        const auto result = port_.receive(rx);
        if (result == ReceiveResult::Error) { fail(LinkFault::PortApi); return; }
        if (!check_time()) return;
        if (result == ReceiveResult::Empty) break;
        record(EventKind::Rx, 0, rx.frame);
        // RX is never promoted before observing newly coalesced faults/completion.
        if (!check_health()) return;
        robot_core::mks::Frame frame;
        frame.id = rx.frame.id <= 0x7FF ? static_cast<std::uint16_t>(rx.frame.id) : 0;
        frame.dlc = rx.frame.dlc;
        frame.data = rx.frame.data;
        frame.extended = rx.frame.extended || rx.frame.id > 0x7FF;
        frame.rtr = rx.frame.rtr;
        core_.on_frame(port_.now_ms(), rx.dequeued_at, frame);
        if (!check_core()) return;
    }
    if (!check_health()) return; // Also runs after a core terminal transition.
    PortStatus tail;
    if (!port_.status(tail)) { fail(LinkFault::PortApi); return; }
    if (!check_time()) return;
    // A new error can appear between the last alert read and this status read.
    if (tail.state == BusState::BusOff || tail.state == BusState::Recovering) {
        fail(LinkFault::BusOff); return;
    }
    if (tail.rx_missed || tail.rx_overrun) { fail(LinkFault::RxLoss); return; }
    if (!error_counters_clear(tail) || tail.state != BusState::Running) {
        fail(LinkFault::BusFault); return;
    }
    if (tail.rx_pending != 0) { fail(LinkFault::RxBacklog); return; }
    core_.tick(port_.now_ms());
    if (!check_core()) return;
    if (core_.state() == StopState::StoppedRecheck) finish(true);
    else dispatch();
}
} // namespace robot_can
