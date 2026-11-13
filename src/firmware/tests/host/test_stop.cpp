#include "test_support.hpp"
#include "robot_core/stop_coordinator.hpp"
#include <algorithm>
#include <array>
#include <cstdint>
#include <limits>
#include <vector>

using namespace robot_core;
namespace {
unsigned scenarios = 0;
void scenario(const char* name) { ++scenarios; std::cout << "STOP " << name << '\n'; }
StopProfile approved(std::uint8_t count = 2, std::uint16_t first = 1) {
    StopProfile p;
    p.axis_count = count; p.axes = {first, 2};
    p.heartbeat_1000_readback_confirmed = true;
    p.response_bounds_approved = true;
    p.position_tolerance_approved = true;
    p.tolerance_counts = 2;
    return p;
}
// Independent fixture construction, not the production encoder/parser.
mks::Frame reply(std::uint16_t axis, std::uint8_t code, std::int64_t value) {
    mks::Frame f; f.id = axis; f.data[0] = code;
    const unsigned bytes = code == 0x31 ? 6 : code == 0x32 ? 2 : 1;
    f.dlc = static_cast<std::uint8_t>(bytes + 2);
    const auto bits = static_cast<std::uint64_t>(value);
    for (unsigned i = 0; i < bytes; ++i)
        f.data[1 + i] = static_cast<std::uint8_t>(bits >> (8 * (bytes - 1 - i)));
    unsigned sum = axis;
    for (unsigned i = 0; i < f.dlc - 1u; ++i) sum += f.data[i];
    f.data[f.dlc - 1] = static_cast<std::uint8_t>(sum);
    return f;
}
StopAction action(StopCoordinator& c, StopAction::Kind expected, std::uint64_t now) {
    StopAction a;
    CHECK(c.take_action(now, a)); CHECK(a.kind == expected); return a;
}
void expect_fault(const StopCoordinator& c, StopFault reason) {
    CHECK(c.state() == StopState::Fault); CHECK(c.fault() == reason);
}
void enter_quiet(StopCoordinator& c) {
    c.begin(0, approved(1)); action(c, StopAction::Kind::Isolate, 0);
    c.on_isolated(1, true);
    const auto a = action(c, StopAction::Kind::Transmit, 1);
    c.on_tx_result(2, a.token, true);
    c.on_frame(3, 3, reply(1, 0xF7, 1));
    CHECK(c.state() == StopState::Quiet);
}
struct Event {
    std::uint64_t at, rx_at;
    int kind; // 0 isolate, 1 TX, 2 RX
    std::uint32_t token;
    mks::Frame frame;
};
enum class Damage { None, Checksum, Id, Dlc, Flags, Unsupported, OldTimestamp,
                    MovingSpeed, MovingRun, FailedRun, Position, Drop, RejectStop };
struct Sim {
    StopCoordinator c;
    StopProfile profile{approved()};
    std::vector<Event> events;
    std::vector<std::pair<std::uint64_t, StopAction>> transmissions;
    std::array<unsigned, 3> position_samples{};
    std::uint64_t isolation_delay{1}, tx_delay{1}, ack_delay{1}, read_delay{1};
    std::uint64_t process_delay{0}, slip{0}, last_stop_tx{0};
    bool repeat_stop{false}, duplicates{false}, noise{false};
    Damage damage{Damage::None};
    std::uint64_t finished{0};

    void drain(std::uint64_t now) {
        StopAction a;
        while (c.take_action(now, a)) {
            if (a.kind == StopAction::Kind::Isolate) {
                events.push_back({now + isolation_delay, 0, 0, 0, {}}); continue;
            }
            transmissions.emplace_back(now, a);
            const auto code = a.frame.data[0];
            CHECK(code == 0xF7 || code == 0x31 || code == 0xF1 || code == 0x32 || code == 0x3A);
            const auto tx = now + tx_delay;
            events.push_back({tx, 0, 1, a.token, {}});
            if (code == 0xF7) last_stop_tx = tx;
            else CHECK(now >= last_stop_tx + 1300);
            std::int64_t value = code == 0x31 ? 100 : code == 0x32 ? 0 : 1;
            if (code == 0x31 && damage == Damage::Position)
                value += 10 * position_samples[a.frame.id]++;
            if (code == 0x32 && damage == Damage::MovingSpeed) value = -1;
            if (code == 0xF1 && damage == Damage::MovingRun) value = 4;
            if (code == 0xF1 && damage == Damage::FailedRun) value = 0;
            if (code == 0xF7 && damage == Damage::RejectStop) value = 0;
            auto f = reply(a.frame.id, code, value);
            auto received = tx + (code == 0xF7 ? ack_delay : read_delay);
            if (code == 0x31) {
                if (damage == Damage::Drop) continue;
                if (damage == Damage::Checksum) f.data[f.dlc - 1] ^= 1;
                if (damage == Damage::Id) f.id = 3;
                if (damage == Damage::Dlc) f.dlc = 7;
                if (damage == Damage::Flags) f.extended = true;
                if (damage == Damage::Unsupported) f = reply(a.frame.id, 0xF3, 1);
            }
            const auto stamp = code == 0x31 && damage == Damage::OldTimestamp ? tx - 1 : received;
            events.push_back({received + process_delay, stamp, 2, 0, f});
            if (duplicates) events.push_back({received + process_delay, stamp, 2, 0, f});
            if (noise) events.push_back({received + process_delay, stamp, 2, 0, reply(3, code, value)});
        }
    }
    void run() {
        c.begin(0, profile); drain(0);
        for (std::uint64_t now = 0; now <= 3600; ++now) {
            for (std::size_t i = 0; i < events.size();) {
                if (events[i].at != now) { ++i; continue; }
                const auto e = events[i]; events.erase(events.begin() + static_cast<std::ptrdiff_t>(i));
                if (e.kind == 0) c.on_isolated(now, true);
                else if (e.kind == 1) c.on_tx_result(now, e.token, true);
                else c.on_frame(now, e.rx_at, e.frame);
                drain(now);
            }
            if (repeat_stop) {
                c.request_stop(now); CHECK(c.started_at() == 0); CHECK(c.deadline() == 3600);
            }
            const auto v = last_stop_tx + 1300;
            const bool skip = slip && now >= v && (now - v) % 60 < slip;
            if (!skip) c.tick(now);
            drain(now);
            if (c.state() == StopState::Fault || c.state() == StopState::StoppedRecheck) {
                finished = now; break;
            }
        }
        std::array<unsigned, 3> stops{};
        for (const auto& sent : transmissions)
            if (sent.second.frame.data[0] == 0xF7) ++stops[sent.second.frame.id];
        CHECK(stops[1] <= 1); CHECK(stops[2] <= 1);
    }
};
}

void run_stop_tests() {
    for (const auto p : {approved(1, 1), approved(1, 2), approved(2)}) {
        scenario("normal axis set / quiet silence / exactly three diagnostic rounds");
        Sim s; s.profile = p; s.run(); CHECK(s.c.state() == StopState::StoppedRecheck);
        CHECK(s.transmissions.size() == static_cast<std::size_t>(13 * p.axis_count));
        CHECK(s.c.issued_stop_count() == p.axis_count);
        CHECK(s.finished < 3600);
        s.c.begin(4000, p); s.c.request_stop(5000); s.c.tick(6000);
        CHECK(s.c.state() == StopState::StoppedRecheck); CHECK(s.c.started_at() == 0);
    }
    for (const auto p : {approved(1, 1), approved(1, 2), approved(2)}) {
        scenario("all delays just before limits / overlapping distinct pending / repeat stop");
        Sim s; s.profile = p; s.isolation_delay = 99; s.tx_delay = 49;
        s.ack_delay = 199; s.read_delay = 109; s.slip = 9;
        s.repeat_stop = s.duplicates = s.noise = true; s.run();
        CHECK(s.c.state() == StopState::StoppedRecheck); CHECK(s.finished < 3600);
        CHECK(s.finished - s.c.verification_start() < 1700);
    }
    scenario("dequeue and processing timestamps remain distinct");
    { Sim s; s.read_delay = 99; s.process_delay = 9; s.run();
      CHECK(s.c.state() == StopState::StoppedRecheck); }
    scenario("default profile cannot begin");
    { StopCoordinator c; c.begin(0, {}); expect_fault(c, StopFault::ProfileUnapproved); }
    for (unsigned flag = 0; flag < 4; ++flag) {
        scenario("each profile approval and tolerance range is mandatory");
        auto p = approved();
        if (flag == 0) p.heartbeat_1000_readback_confirmed = false;
        if (flag == 1) p.response_bounds_approved = false;
        if (flag == 2) p.position_tolerance_approved = false;
        if (flag == 3) p.tolerance_counts = std::numeric_limits<std::uint64_t>::max();
        StopCoordinator c; c.begin(0, p); expect_fault(c, StopFault::ProfileUnapproved);
    }
    for (const auto axes : {std::array<std::uint16_t, 2>{2, 1}, {1, 1}, {1, 3}}) {
        scenario("invalid two-axis order or duplicate");
        auto p = approved(); p.axes = axes; StopCoordinator c; c.begin(0, p);
        expect_fault(c, StopFault::InvalidAxes);
    }
    for (const std::uint8_t count : {0, 3}) {
        scenario("invalid axis count"); auto p = approved(); p.axis_count = count;
        StopCoordinator c; c.begin(0, p); expect_fault(c, StopFault::InvalidAxes);
    }
    scenario("isolation exact 100 ms loses to timeout");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(100, true); expect_fault(c, StopFault::IsolationTimeout); }
    scenario("isolation explicit failure and terminal persistence");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, false); c.begin(10, approved()); c.request_stop(20);
      expect_fault(c, StopFault::IsolationFailed); StopAction a; CHECK(!c.take_action(20, a)); }
    scenario("undrained isolation action cannot be acknowledged");
    { StopCoordinator c; c.begin(0, approved()); c.on_isolated(1, true);
      expect_fault(c, StopFault::ActionNotConsumed); }
    scenario("preparation exact 600 ms");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); action(c, StopAction::Kind::Transmit, 1); c.tick(600);
      expect_fault(c, StopFault::PreparationTimeout); }
    scenario("verification exact 1700 ms on delayed wake");
    { StopCoordinator c; enter_quiet(c); c.tick(3002);
      expect_fault(c, StopFault::VerificationTimeout); }
    scenario("overall exact 3600 ms");
    { StopCoordinator c; enter_quiet(c); c.tick(3600); expect_fault(c, StopFault::OverallTimeout); }
    scenario("TX exact 50 ms and matching success token cannot win");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); auto a = action(c, StopAction::Kind::Transmit, 1);
      c.on_tx_result(51, a.token, true); expect_fault(c, StopFault::TxTimeout); }
    scenario("ACK exact 200 ms cannot win");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); auto a = action(c, StopAction::Kind::Transmit, 1);
      c.on_tx_result(2, a.token, true); c.on_frame(202, 202, reply(1, 0xF7, 1));
      expect_fault(c, StopFault::ResponseTimeout); }
    scenario("read exact 110 ms cannot win");
    { StopCoordinator c; enter_quiet(c); c.tick(1302); auto a = action(c, StopAction::Kind::Transmit, 1302);
      c.on_tx_result(1303, a.token, true); c.on_frame(1413, 1413, reply(1, 0x31, 0));
      expect_fault(c, StopFault::ResponseTimeout); }
    scenario("first diagnostic slot 10 ms late cannot move schedule");
    { StopCoordinator c; enter_quiet(c); c.tick(1312); expect_fault(c, StopFault::SlotMissed); }
    scenario("F7 handoff at exact TX expiry fails without an intervening tick");
    { StopCoordinator c; c.begin(0, approved(1)); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); StopAction a; CHECK(!c.take_action(51, a));
      expect_fault(c, StopFault::TxTimeout); }
    scenario("diagnostic handoff at exact slot expiry fails without an intervening tick");
    { StopCoordinator c; enter_quiet(c); c.tick(1302); StopAction a;
      CHECK(!c.take_action(1312, a)); expect_fault(c, StopFault::SlotMissed); }
    scenario("diagnostic handoff just before expiry retains original TX deadline");
    { StopCoordinator c; enter_quiet(c); c.tick(1302);
      auto a = action(c, StopAction::Kind::Transmit, 1311);
      CHECK(a.dispatch_before == 1312); c.on_tx_result(1352, a.token, true);
      expect_fault(c, StopFault::TxTimeout); }
    scenario("diagnostic handoff at 9 ms and timely TX can proceed");
    { StopCoordinator c; enter_quiet(c); c.tick(1302);
      auto a = action(c, StopAction::Kind::Transmit, 1311);
      c.on_tx_result(1312, a.token, true); c.on_frame(1313, 1313, reply(1, 0x31, 0));
      CHECK(c.state() == StopState::Verifying); }
    scenario("isolation handoff cannot escape its timeout");
    { StopCoordinator c; c.begin(0, approved()); StopAction a; CHECK(!c.take_action(100, a));
      expect_fault(c, StopFault::IsolationTimeout); }
    scenario("quiet remains entirely silent");
    { StopCoordinator c; enter_quiet(c); for (std::uint64_t t = 4; t < 1302; ++t) {
        c.tick(t); c.on_frame(t, t, reply(1, 0x31, 0)); StopAction a; CHECK(!c.take_action(t, a));
      } CHECK(c.state() == StopState::Quiet); }
    scenario("ACK before TX notification is not remembered");
    { StopCoordinator c; c.begin(0, approved(1)); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); auto a = action(c, StopAction::Kind::Transmit, 1);
      c.on_frame(2, 2, reply(1, 0xF7, 1)); c.on_tx_result(3, a.token, true); c.tick(203);
      expect_fault(c, StopFault::ResponseTimeout); }
    scenario("TX failure");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); auto a = action(c, StopAction::Kind::Transmit, 1);
      c.on_tx_result(2, a.token, false); expect_fault(c, StopFault::TxFailed); }
    scenario("unknown TX token");
    { StopCoordinator c; c.begin(0, approved()); action(c, StopAction::Kind::Isolate, 0);
      c.on_isolated(1, true); auto a = action(c, StopAction::Kind::Transmit, 1);
      c.on_tx_result(2, a.token + 1, true); expect_fault(c, StopFault::UnknownTxToken); }
    scenario("stale TX completion after quiet");
    { StopCoordinator c; enter_quiet(c); c.on_tx_result(4, 1, true);
      expect_fault(c, StopFault::UnknownTxToken); }
    scenario("bus-off discards unsent action");
    { StopCoordinator c; c.begin(0, approved()); c.on_bus_off(1);
      expect_fault(c, StopFault::BusOff); StopAction a; CHECK(!c.take_action(1, a)); }
    scenario("receive overflow");
    { StopCoordinator c; enter_quiet(c); c.on_receive_overflow(4);
      expect_fault(c, StopFault::ReceiveOverflow); }
    scenario("clock reversal");
    { StopCoordinator c; enter_quiet(c); c.tick(2); expect_fault(c, StopFault::ClockReversed); }
    scenario("clock addition overflow");
    { StopCoordinator c; c.begin(std::numeric_limits<std::uint64_t>::max() - 3599, approved());
      expect_fault(c, StopFault::TimeOverflow); }
    scenario("latest representable start works through quiet");
    { const auto start = std::numeric_limits<std::uint64_t>::max() - 3600;
      StopCoordinator c; c.begin(start, approved(1)); action(c, StopAction::Kind::Isolate, start);
      c.on_isolated(start + 1, true); auto a = action(c, StopAction::Kind::Transmit, start + 1);
      c.on_tx_result(start + 2, a.token, true); c.on_frame(start + 3, start + 3, reply(1, 0xF7, 1));
      c.tick(start + 1302); CHECK(c.state() == StopState::Verifying); }
    scenario("RX processing exact 10 ms");
    { StopCoordinator c; enter_quiet(c); c.on_frame(20, 10, reply(1, 0x31, 0));
      expect_fault(c, StopFault::ReceiveDelay); }
    scenario("future RX timestamp");
    { StopCoordinator c; enter_quiet(c); c.on_frame(4, 5, reply(1, 0x31, 0));
      expect_fault(c, StopFault::ReceiveDelay); }
    for (const auto damage : {Damage::Checksum, Damage::Id, Damage::Dlc, Damage::Flags,
                             Damage::Unsupported, Damage::Drop}) {
        scenario("invalid/missing responses never refresh pending");
        Sim s; s.damage = damage; s.run(); expect_fault(s.c, StopFault::ResponseTimeout);
    }
    scenario("old dequeued frame cannot satisfy a newer pending request");
    { Sim s; s.damage = Damage::OldTimestamp; s.read_delay = 1; s.run();
      expect_fault(s.c, StopFault::ResponseTimeout); }
    for (const auto damage : {Damage::MovingSpeed, Damage::MovingRun, Damage::FailedRun}) {
        scenario("any moving/failed observation prevents promotion");
        Sim s; s.damage = damage; s.run(); expect_fault(s.c, StopFault::Moving);
    }
    scenario("three positions must be stable");
    { Sim s; s.damage = Damage::Position; s.run(); expect_fault(s.c, StopFault::UnstablePosition); }
    scenario("F7 negative acknowledgement");
    { Sim s; s.damage = Damage::RejectStop; s.run(); expect_fault(s.c, StopFault::StopRejected); }
    std::cout << "STOP_SCENARIOS=" << scenarios << '\n';
}
