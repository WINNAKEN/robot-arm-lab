#include "robot_can/stop_link.hpp"
#include "test_support.hpp"
#include <deque>
#include <vector>
#include <type_traits>
#include <limits>

using namespace robot_can;
using robot_core::StopState;
namespace {
unsigned cases = 0;
void scenario(const char* name) { ++cases; std::cout << "LINK " << name << '\n'; }
robot_core::StopProfile approved(unsigned count = 2, unsigned first = 1) {
    robot_core::StopProfile p;
    p.axis_count = static_cast<std::uint8_t>(count);
    p.axes[0] = static_cast<std::uint16_t>(first);
    p.heartbeat_1000_readback_confirmed = p.response_bounds_approved = p.position_tolerance_approved = true;
    p.tolerance_counts = 2;
    return p;
}
// Construct protocol bytes independently from the production codec.
WireFrame response(std::uint32_t id, std::uint8_t code) {
    WireFrame f; f.id = id; f.data[0] = code;
    const unsigned bytes = code == 0x31 ? 6 : code == 0x32 ? 2 : 1;
    f.dlc = static_cast<std::uint8_t>(bytes + 2);
    f.data[bytes] = code == 0x31 ? 100 : code == 0x32 ? 0 : 1;
    unsigned sum = id;
    for (unsigned i = 0; i < f.dlc - 1u; ++i) sum += f.data[i];
    f.data[f.dlc - 1u] = static_cast<std::uint8_t>(sum);
    return f;
}
struct Sent { std::uint64_t at; WireFrame frame; };
class FakePort final : public CanPort {
public:
    std::uint64_t time{0}, open_delay{0}, close_delay{0}, receive_delay{0}, submit_delay{0};
    std::uint64_t status_delay{0}, alerts_delay{0};
    bool open_ok{true}, alerts_ok{true}, status_ok{true}, receive_ok{true}, submit_ok{true};
    bool auto_answer{true}, active{false}, duplicate{false};
    bool damage_checksum{false}, damage_id{false}, damage_flags{false}, damage_dlc{false};
    bool final_rx_error{false}, error_after_receive{false}, refill_rx{false};
    bool final_alert_error{false};
    CloseResult closing{true, true};
    unsigned opens{0}, closes{0}, submissions{0}, receives{0}, status_reads{0}, inject_rx_status{0};
    std::uint32_t alerts{0};
    PortStatus stat{};
    std::deque<RxFrame> rx;
    std::vector<Sent> sent;
    std::uint64_t scheduled_at{0};
    WireFrame scheduled_frame{};
    bool scheduled{false};
    std::uint64_t now_ms() const noexcept override { return time; }
    bool reset_and_start() noexcept override {
        ++opens; time += open_delay;
        active = open_ok; stat.state = BusState::Running;
        return open_ok;
    }
    CloseResult close() noexcept override {
        ++closes; time += close_delay; active = false; return closing;
    }
    void ready() {
        if (scheduled && time >= scheduled_at) {
            scheduled = false; stat.tx_pending = 0; alerts |= TxSuccess | TxIdle;
            auto f = response(scheduled_frame.id, scheduled_frame.data[0]);
            if (damage_checksum) f.data[f.dlc - 1u] ^= 1;
            if (damage_id) f.id = 0x10001;
            if (damage_flags) f.extended = true;
            if (damage_dlc) f.dlc = 9;
            rx.push_back({f, time});
            if (duplicate) rx.push_back({f, time});
        }
    }
    bool read_alerts(std::uint32_t& out) noexcept override {
        time += alerts_delay; ready();
        if (final_alert_error && receives == 26) alerts |= BusOff;
        out = alerts; alerts = 0; return alerts_ok;
    }
    bool status(PortStatus& out) noexcept override {
        if (++status_reads == inject_rx_status) rx.push_back({response(1,0xF7),time});
        time += status_delay; stat.rx_pending = static_cast<std::uint32_t>(rx.size());
        out = stat; return status_ok;
    }
    ReceiveResult receive(RxFrame& out) noexcept override {
        time += receive_delay;
        if (!receive_ok) return ReceiveResult::Error;
        if (rx.empty()) return ReceiveResult::Empty;
        out = rx.front(); rx.pop_front(); ++receives;
        // This is dequeue time, not the fixture's simulated wire delivery time.
        out.dequeued_at = time;
        if (refill_rx) rx.push_back(out);
        if (error_after_receive || (final_rx_error && receives == 26)) stat.rx_missed = 1;
        return ReceiveResult::Data;
    }
    bool submit(const WireFrame& frame, std::uint64_t before) noexcept override {
        CHECK(active); CHECK(stat.tx_pending == 0); CHECK(time < before);
        ++submissions; sent.push_back({time, frame}); time += submit_delay;
        stat.tx_pending = 1;
        if (auto_answer) {
            scheduled = true; scheduled_at = time + 1; scheduled_frame = frame;
        }
        return submit_ok; // Fake may deliberately violate post-call deadline checking.
    }
};

void complete(FakePort& port, StopLink& link, bool repeat = false) {
    for (unsigned i = 0; i < 3700 && link.state() == LinkState::Active; ++i) {
        ++port.time;
        if (repeat) link.request_stop(); else link.poll();
    }
}
void faulted(FakePort& port, StopLink& link, LinkFault fault) {
    CHECK(link.state() == LinkState::Fault); CHECK(link.fault() == fault);
    const auto tx = port.submissions;
    link.poll(); link.begin_stop(approved()); link.request_stop();
    CHECK(port.submissions == tx); CHECK(port.closes <= 1);
}
}

int main() {
    static_assert(!std::is_copy_constructible_v<StopLink>);
    for (const auto p : {approved(1, 1), approved(1, 2), approved(2)}) {
        scenario("normal axes / ACK with completion / quiet / three rounds / terminal lock");
        FakePort port; StopLink link(port); CHECK(port.opens == 0);
        link.begin_stop(p); complete(port, link, true);
        CHECK(link.state() == LinkState::StoppedRecheck);
        CHECK(link.core().state() == StopState::StoppedRecheck);
        CHECK(port.sent.size() == 13u * p.axis_count); CHECK(port.closes == 1);
        CHECK(link.close_result().quiesced); CHECK(link.close_result().healthy);
        std::uint64_t last_f7 = 0;
        unsigned stops = 0;
        for (const auto& s : port.sent) {
            if (s.frame.data[0] == 0xF7) { last_f7 = s.at; ++stops; }
            else { CHECK(s.at >= last_f7 + 1301); CHECK(s.frame.data[0] != 0xF3); CHECK(s.frame.data[0] != 0xFD); }
        }
        CHECK(stops == p.axis_count); CHECK(link.core().started_at() == 0);
        CHECK(link.core().deadline() == 3600);
        link.begin_stop(p); link.poll(); CHECK(port.opens == 1); CHECK(port.closes == 1);
    }
    scenario("unapproved profile does not touch driver");
    { FakePort p; StopLink l(p); l.begin_stop({}); faulted(p,l,LinkFault::Core);
      CHECK(p.opens == 0); CHECK(p.closes == 0); CHECK(p.submissions == 0); }
    scenario("uint64 overflow rejects before driver");
    { FakePort p; p.time = std::numeric_limits<std::uint64_t>::max(); StopLink l(p);
      l.begin_stop(approved()); faulted(p,l,LinkFault::Core); CHECK(p.opens == 0); }
    for (const auto delay : {99u,100u}) {
        scenario("isolation boundary 99/100");
        FakePort p; p.open_delay=delay; StopLink l(p); l.begin_stop(approved());
        if (delay == 99) { complete(p,l); CHECK(l.state()==LinkState::StoppedRecheck); }
        else { faulted(p,l,LinkFault::Core); CHECK(p.submissions==0); }
    }
    scenario("isolation failure cleanup");
    { FakePort p; p.open_ok=false; StopLink l(p); l.begin_stop(approved());
      faulted(p,l,LinkFault::Core); CHECK(p.closes==1); CHECK(p.submissions==0); }
    scenario("accepted TX without completion times out; no retries");
    { FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved()); complete(p,l);
      faulted(p,l,LinkFault::Core); CHECK(l.core().fault()==robot_core::StopFault::TxTimeout); CHECK(p.submissions==1); }
    scenario("idle-only alert is not completion");
    { FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
      p.alerts=TxIdle; ++p.time; l.poll(); CHECK(l.core().state()==StopState::StopCommands);
      complete(p,l); faulted(p,l,LinkFault::Core); }
    for (const auto bits : {TxSuccess|TxFailed, TxSuccess|BusOff, TxSuccess|RxQueueFull,
                           TxSuccess|RxFifoOverrun, TxSuccess|ErrorPassive,
                           TxSuccess|PeripheralReset, TxSuccess|TxRetried,
                           TxSuccess|BusError, TxSuccess|AboveErrorWarning, TxSuccess|ArbitrationLost}) {
        scenario("coalesced fatal wins over successful TX");
        FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
        p.stat.tx_pending=0; p.alerts=bits; ++p.time; l.poll();
        CHECK(l.state()==LinkState::Fault); CHECK(l.core().state()!=StopState::Quiet); CHECK(p.submissions==1);
    }
    scenario("TX_FAILED terminal reports core failure");
    { FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
      p.stat.tx_pending=0; p.alerts=TxFailed; ++p.time; l.poll(); faulted(p,l,LinkFault::Core); }
    scenario("completion with tx_pending still occupied");
    { FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
      p.alerts=TxSuccess; ++p.time; l.poll(); faulted(p,l,LinkFault::UnexpectedCompletion); }
    scenario("unexpected old completion before first submit");
    { FakePort p; p.alerts=TxSuccess; StopLink l(p); l.begin_stop(approved());
      faulted(p,l,LinkFault::UnexpectedCompletion); CHECK(p.submissions==0); }
    scenario("known queued RX before submit cannot enter a new response window");
    { FakePort p; p.inject_rx_status=2; StopLink l(p); l.begin_stop(approved());
      faulted(p,l,LinkFault::RxBacklog); CHECK(p.submissions==0); }
    scenario("late duplicate completion in quiet");
    { FakePort p; StopLink l(p); l.begin_stop(approved(1)); ++p.time; l.poll();
      CHECK(l.core().state()==StopState::Quiet); p.alerts=TxSuccess; ++p.time; l.poll();
      faulted(p,l,LinkFault::UnexpectedCompletion); }
    for (unsigned counter=0; counter<5; ++counter) {
        scenario("counter evidence without alert");
        FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
        std::uint32_t* counters[] = {&p.stat.rx_missed,&p.stat.rx_overrun,&p.stat.tx_failed,&p.stat.bus_errors,&p.stat.arbitration_lost};
        *counters[counter]=1; ++p.time; l.poll(); CHECK(l.state()==LinkState::Fault);
    }
    for (const auto state : {BusState::Stopped,BusState::BusOff,BusState::Recovering}) {
        scenario("non-running state is not healthy");
        FakePort p; StopLink l(p); l.begin_stop(approved()); p.stat.state=state;
        ++p.time; l.poll(); CHECK(l.state()==LinkState::Fault);
    }
    for (unsigned api=0; api<4; ++api) {
        scenario("I/O API failure"); FakePort p; StopLink l(p);
        if (api==0) p.submit_ok=false;
        l.begin_stop(approved());
        if (api==1) p.alerts_ok=false;
        if (api==2) p.status_ok=false;
        if (api==3) p.receive_ok=false;
        ++p.time; l.poll(); CHECK(l.state()==LinkState::Fault); CHECK(p.closes==1);
    }
    for (const auto gap : {9u,10u}) {
        scenario("poll gap 9/10ms"); FakePort p; StopLink l(p); l.begin_stop(approved(1));
        p.time=gap; l.poll();
        if (gap==9) CHECK(l.state()==LinkState::Active); else faulted(p,l,LinkFault::ServiceGap);
    }
    scenario("clock reversed");
    { FakePort p; p.time=100; StopLink l(p); l.begin_stop(approved()); p.time=99;
      l.poll(); faulted(p,l,LinkFault::Clock); }
    for (unsigned slow=0;slow<4;++slow) {
        scenario("long port call invalidates observation or accepted submission");
        FakePort p; if(slow==0) p.submit_delay=10; StopLink l(p); l.begin_stop(approved());
        if(slow==1) p.receive_delay=10;
        if(slow==2) p.status_delay=10;
        if(slow==3) p.alerts_delay=10;
        ++p.time; l.poll(); faulted(p,l,LinkFault::ServiceGap); CHECK(p.submissions==1);
    }
    scenario("RX error after dequeue beats reply");
    { FakePort p; p.error_after_receive=true; StopLink l(p); l.begin_stop(approved());
      ++p.time; l.poll(); faulted(p,l,LinkFault::RxLoss); CHECK(p.submissions==1); }
    scenario("bounded RX batch cannot drain an endless source");
    { FakePort p; p.refill_rx=true; StopLink l(p); l.begin_stop(approved(1));
      ++p.time; l.poll(); faulted(p,l,LinkFault::RxBacklog); CHECK(p.receives==16); }
    scenario("oversize RX queue rejects before promotion");
    { FakePort p; p.auto_answer=false; StopLink l(p); l.begin_stop(approved());
      for(unsigned i=0;i<17;++i) p.rx.push_back({response(1,0xF7),0});
      ++p.time; l.poll(); faulted(p,l,LinkFault::RxBacklog); CHECK(p.receives==0); }
    for (unsigned damage=0;damage<4;++damage) {
        scenario("malformed response never satisfies ACK"); FakePort p;
        p.damage_checksum=damage==0; p.damage_id=damage==1; p.damage_flags=damage==2; p.damage_dlc=damage==3;
        StopLink l(p); l.begin_stop(approved(1)); complete(p,l); faulted(p,l,LinkFault::Core);
        CHECK(l.core().fault()==robot_core::StopFault::ResponseTimeout);
        if(damage==1) { bool found=false; LogEvent e;
            for(std::size_t i=0;i<l.log_size();++i) if(l.log_at(i,e)&&e.kind==EventKind::Rx&&e.frame.id==0x10001) found=true;
            CHECK(found); }
    }
    scenario("duplicate frames remain harmless within bounded batch");
    { FakePort p; p.duplicate=true; StopLink l(p); l.begin_stop(approved()); complete(p,l);
      CHECK(l.state()==LinkState::StoppedRecheck); }
    for (unsigned final_fault=0;final_fault<6;++final_fault) {
        scenario("final RX/close evidence cannot be lost behind terminal core");
        FakePort p;
        if(final_fault==0) p.final_rx_error=true;
        if(final_fault==1) p.final_alert_error=true;
        if(final_fault==2) p.closing={true,false};
        if(final_fault==3) p.closing={false,true};
        if(final_fault==4) p.close_delay=10;
        if(final_fault==5) p.close_delay=4000;
        StopLink l(p); l.begin_stop(approved()); complete(p,l);
        CHECK(l.state()==LinkState::Fault); CHECK(p.closes==1);
        if(final_fault>=2) CHECK(l.core().state()==StopState::StoppedRecheck);
    }
    scenario("close at 9ms remains within service budget");
    { FakePort p; p.close_delay=9; StopLink l(p); l.begin_stop(approved()); complete(p,l);
      CHECK(l.state()==LinkState::StoppedRecheck); }
    scenario("bounded raw log exposes overwrite count and preserves recent events");
    { FakePort p; StopLink l(p); l.begin_stop(approved(1)); ++p.time; l.poll();
      for(unsigned i=0;i<80;++i) { p.rx.push_back({response(123,0xF1),p.time}); ++p.time; l.poll(); }
      CHECK(l.state()==LinkState::Active); CHECK(l.log_size()==64); CHECK(l.overwritten_events()>0);
      LogEvent e; CHECK(l.log_at(63,e)); CHECK(e.kind==EventKind::Rx); CHECK(e.frame.id==123); CHECK(!l.log_at(64,e)); }
    std::cout << "LINK scenarios=" << cases << " assertions=" << check_count << " PASS\n";
    return 0;
}
