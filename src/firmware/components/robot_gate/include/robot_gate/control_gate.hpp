#pragma once
#include <array>
#include <cstdint>
namespace robot_gate {
using Id = std::uint64_t;
struct Config { Id boot{0}, profile{0}; std::array<std::uint16_t,2> axes{1,2}; std::uint8_t count{2}; };
struct Axis { std::uint16_t id{0}; bool valid{false}, enabled{false}, moving{false}; };
struct Snapshot {
    Id revision{0}, profile{0}; std::uint8_t count{2};
    std::array<Axis,2> axes{{{1,false,false,false},{2,false,false,false}}};
    bool approved{false}, ready{false}, stopped{false}, moving{false}, stop{false}, fault{false};
};
enum class Op : std::uint8_t { Acquire, Renew, Arm, Ticket, Move, Release, Stop };
enum class Error : std::uint8_t {
    None, ConfigInvalid, ProfileChanged, SnapshotInvalid, ClockReversed, Overflow,
    IdentityExhausted, SessionFull, BadSession, BadBoot, Replay, BadLease,
    Denied, Busy, AxisDenied, BadTicket, BadRequest, Expired, Stopping, CompletionInvalid
};
struct Request {
    Id boot{0}, session{0}, seq{0}, request{0}, lease{0}, ticket{0};
    Op op{Op::Acquire}; std::uint16_t axis{0}; std::uint8_t direction{0};
};
struct Intent {
    Id id{0}, boot{0}, session{0}, lease{0}, revision{0}, dispatch_before{0};
    std::uint16_t axis{0}, pulses{100}; std::uint8_t direction{0}, speed{5}, acceleration{2};
};
struct Result { Error error{Error::None}; Id lease{0}, ticket{0}; };
struct Status {
    Error error{Error::None}; Id revision{0}, owner{0}, lease{0}, lease_until{0}, stop_started_at{0};
    std::uint16_t armed_axis{0}; bool stopped_latched{false}, fault{false}, reserved{false}, dispatched{false};
};
// Serialized single owner, typed adapter boundary. No I/O, allocation or clock calls.
class ControlGate {
public:
    explicit ControlGate(const Config& config) noexcept;
    ControlGate(const ControlGate&) = delete;
    ControlGate& operator=(const ControlGate&) = delete;
    ControlGate(ControlGate&&) = delete;
    ControlGate& operator=(ControlGate&&) = delete;
    Id open_session(Id now, const Snapshot& snapshot) noexcept;
    void close_session(Id now, const Snapshot& snapshot, Id session) noexcept;
    Result handle(Id now, const Snapshot& snapshot, const Request& request) noexcept;
    void tick(Id now, const Snapshot& snapshot) noexcept;
    bool take_intent(Id now, const Snapshot& snapshot, Intent& out) noexcept;
    bool take_stop(Id now, const Snapshot& snapshot, Id& started_at) noexcept;
    bool complete(Id now, const Snapshot& snapshot, Id intent) noexcept;
    Status status() const noexcept;
private:
    struct Session { Id id{0}, seq{0}, request{0}; };
    bool advance(Id now, const Snapshot& snapshot) noexcept;
    bool healthy() const noexcept;
    bool stopped() const noexcept;
    bool enabled(std::uint16_t axis) const noexcept;
    bool same(const Snapshot& other) const noexcept;
    Id allocate(Id now) noexcept;
    bool deadline(Id now, Id duration, Id& out) noexcept;
    void stop(Id now, Error error, bool fault=false) noexcept;
    void clear() noexcept;
    bool end_guard(Id now) noexcept;
    Config config_{}; Snapshot snapshot_{};
    std::array<Session,2> sessions_{};
    Id last_now_{0}, next_id_{1}, owner_{0}, lease_{0}, lease_until_{0};
    Id ticket_{0}, ticket_until_{0}, ticket_revision_{0}, stop_at_{0};
    std::uint16_t armed_{0}; Intent intent_{};
    bool seen_time_{false}, seen_snapshot_{false}, stopping_{false}, stop_pending_{false}, fault_{false};
    bool reserved_{false}, dispatched_{false}, pending_{false}; Error error_{Error::None};
};
} // namespace robot_gate
