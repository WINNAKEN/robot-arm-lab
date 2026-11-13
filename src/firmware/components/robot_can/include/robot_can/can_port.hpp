#pragma once
#include <array>
#include <cstdint>

namespace robot_can {
struct WireFrame {
    std::uint32_t id{0};
    std::uint8_t dlc{0};
    std::array<std::uint8_t, 8> data{};
    bool extended{false}, rtr{false};
};
struct RxFrame { WireFrame frame{}; std::uint64_t dequeued_at{0}; };
enum class ReceiveResult : std::uint8_t { Data, Empty, Error };
enum class BusState : std::uint8_t { Stopped, Running, BusOff, Recovering };
struct PortStatus {
    BusState state{BusState::Stopped};
    std::uint32_t tx_pending{0}, rx_pending{0}, rx_missed{0}, rx_overrun{0};
    std::uint32_t tx_failed{0}, bus_errors{0}, arbitration_lost{0};
};
enum Alert : std::uint32_t {
    TxSuccess = 1u << 0, TxFailed = 1u << 1, TxIdle = 1u << 2,
    BusOff = 1u << 3, RxQueueFull = 1u << 4, RxFifoOverrun = 1u << 5,
    ErrorPassive = 1u << 6, PeripheralReset = 1u << 7, TxRetried = 1u << 8,
    BusError = 1u << 9, AboveErrorWarning = 1u << 10, ArbitrationLost = 1u << 11
};
constexpr std::uint32_t fatal_alerts = BusOff | RxQueueFull | RxFifoOverrun |
    ErrorPassive | PeripheralReset | TxRetried | BusError | AboveErrorWarning | ArbitrationLost;
constexpr std::uint32_t all_alerts = fatal_alerts | TxSuccess | TxFailed | TxIdle;
inline bool error_counters_clear(const PortStatus& s) noexcept {
    return s.rx_missed == 0 && s.rx_overrun == 0 && s.tx_failed == 0 &&
        s.bus_errors == 0 && s.arbitration_lost == 0;
}
struct CloseResult {
    bool quiesced{false}; // Driver handle was successfully removed.
    bool healthy{false}; // Final observable SW evidence, not a physical stop proof.
};

// Single owner, zero-wait I/O, no concurrent SDK users. Constructors do no I/O.
// reset creates a fresh driver lifetime; failed lifetimes cannot be restarted.
class CanPort {
public:
    CanPort() = default;
    virtual ~CanPort() = default;
    CanPort(const CanPort&) = delete;
    CanPort& operator=(const CanPort&) = delete;
    virtual std::uint64_t now_ms() const noexcept = 0;
    virtual bool reset_and_start() noexcept = 0;
    virtual CloseResult close() noexcept = 0;
    virtual bool read_alerts(std::uint32_t& alerts) noexcept = 0;
    virtual bool status(PortStatus& status) noexcept = 0;
    virtual ReceiveResult receive(RxFrame& frame) noexcept = 0;
    // Acceptance is NOT TX completion. Check time immediately before and after SDK call.
    virtual bool submit(const WireFrame& frame, std::uint64_t dispatch_before) noexcept = 0;
};
} // namespace robot_can
