#include "robot_twai/idf_twai_port.hpp"
#include "stub_sdk.hpp"
#include <cstdlib>
#include <iostream>
#include <limits>
#include <type_traits>

namespace {
unsigned assertions = 0, cases = 0;
const char* current_case = "";
void check(bool value, const char* expression, int line) {
    ++assertions;
    if (!value) {
        std::cerr << current_case << ':' << line << " FAILED: " << expression << '\n';
        std::exit(1);
    }
}
#define CHECK(x) check(static_cast<bool>(x), #x, __LINE__)
template<class Fn> void scenario(const char* name, Fn run) {
    stub::reset(); current_case = name; run(); ++cases;
}
using robot_can::IdfTwaiPort;
using robot_can::WireFrame;
using robot_can::PortStatus;
using robot_can::RxFrame;
using robot_can::ReceiveResult;

void assert_failed_latch(IdfTwaiPort& port) {
    const auto count = stub::f.calls.size();
    std::uint32_t alerts = 9;
    PortStatus s;
    RxFrame rx;
    CHECK(!port.reset_and_start());
    CHECK(!port.read_alerts(alerts)); CHECK(alerts == 0);
    CHECK(!port.status(s));
    CHECK(port.receive(rx) == ReceiveResult::Error);
    CHECK(!port.submit(WireFrame{1, 2, {0xF7, 0xF8}}, 100));
    CHECK(stub::f.calls.size() == count);
}

void basic_configuration() {
    scenario("constructor destructor are inert", [] {
        { IdfTwaiPort port; CHECK(stub::f.calls.empty()); }
        CHECK(stub::f.calls.empty());
        CHECK(!std::is_copy_constructible<IdfTwaiPort>::value);
        CHECK(!std::is_move_constructible<IdfTwaiPort>::value);
    });
    scenario("unopened calls and close", [] {
        IdfTwaiPort p;
        PortStatus s; RxFrame rx; std::uint32_t alerts = 55;
        CHECK(!p.status(s)); CHECK(!p.read_alerts(alerts)); CHECK(alerts == 0);
        CHECK(p.receive(rx) == ReceiveResult::Error);
        CHECK(!p.submit({}, 100)); CHECK(stub::f.calls.empty());
        auto c = p.close(); CHECK(c.quiesced && c.healthy);
        CHECK(stub::f.calls.empty());
    });
    scenario("configuration and fresh lifecycle", [] {
        IdfTwaiPort p;
        CHECK(p.reset_and_start());
        const auto& f = stub::f;
        const std::vector<std::string> expected{"install", "status", "alerts", "start", "status"};
        CHECK(f.calls == expected);
        CHECK(f.general.controller_id == 0 && f.general.mode == TWAI_MODE_NORMAL);
        CHECK(f.general.tx_io == GPIO_NUM_15 && f.general.rx_io == GPIO_NUM_16);
        CHECK(f.general.clkout_io == TWAI_IO_UNUSED && f.general.bus_off_io == TWAI_IO_UNUSED);
        CHECK(f.general.tx_queue_len == 0 && f.general.rx_queue_len == 16);
        CHECK(f.general.clkout_divider == 0 && f.general.general_flags.sleep_allow_pd == 0);
        CHECK(f.general.intr_flags == ESP_INTR_FLAG_LEVEL1);
        CHECK(f.timing.quanta_resolution_hz / (1 + f.timing.tseg_1 + f.timing.tseg_2) == 500000);
        CHECK(f.timing.brp == 0 && !f.timing.triple_sampling);
        CHECK(f.filter.acceptance_code == 0 && f.filter.acceptance_mask == 0xFFFFFFFF);
        CHECK(f.filter.single_filter && f.alerts_wait == 0);
        const auto closed = p.close();
        CHECK(closed.quiesced && closed.healthy && !f.installed);
        const auto count = f.calls.size();
        CHECK(p.close().quiesced && p.close().healthy);
        CHECK(f.calls.size() == count);
    });
    scenario("fresh driver replaces queue and stale alerts", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.alerts = TWAI_ALERT_TX_SUCCESS | TWAI_ALERT_RX_QUEUE_FULL;
        stub::f.status.msgs_to_tx = 1; stub::f.status.msgs_to_rx = 5;
        const auto offset = stub::f.calls.size();
        CHECK(p.reset_and_start());
        const std::vector<std::string> expected{"status", "stop", "status", "uninstall",
            "install", "status", "alerts", "start", "status"};
        CHECK(std::vector<std::string>(stub::f.calls.begin() + static_cast<std::ptrdiff_t>(offset),
            stub::f.calls.end()) == expected);
        CHECK(stub::f.alerts == 0 && stub::f.status.msgs_to_tx == 0 && stub::f.status.msgs_to_rx == 0);
        CHECK(p.close().quiesced);
    });
    scenario("already stopped replacement", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.status.state = TWAI_STATE_STOPPED;
        CHECK(p.reset_and_start()); CHECK(stub::f.call_count["stop"] == 0);
        CHECK(p.close().quiesced);
    });
    for (const auto state : {TWAI_STATE_BUS_OFF, TWAI_STATE_RECOVERING})
        scenario("reset cannot recover failed bus", [state] {
            IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.status.state = state;
            CHECK(!p.reset_and_start()); CHECK(stub::f.call_count["install"] == 1);
            assert_failed_latch(p);
            const auto closed = p.close();
            CHECK(!closed.healthy); CHECK(closed.quiesced == (state == TWAI_STATE_BUS_OFF));
        });
}

void lifecycle_failures() {
    struct Failure { const char* op; unsigned occurrence; };
    const Failure fresh[] = {{"install",1},{"status",1},{"alerts",1},{"start",1},{"status",2}};
    for (const auto f : fresh) scenario("fresh API failure", [f] {
        stub::f.fail_operation = f.op; stub::f.fail_occurrence = f.occurrence;
        IdfTwaiPort p; CHECK(!p.reset_and_start()); assert_failed_latch(p);
        const auto c = p.close(); CHECK(c.quiesced && !c.healthy);
    });
    const Failure old[] = {{"status",3},{"stop",1},{"status",4},{"uninstall",1}};
    for (const auto f : old) scenario("replace API failure", [f] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.fail_operation = f.op; stub::f.fail_occurrence = f.occurrence;
        CHECK(!p.reset_and_start()); CHECK(stub::f.call_count["install"] == 1);
        assert_failed_latch(p); CHECK(p.close().quiesced);
    });
    for (unsigned i = 0; i < 9; ++i) scenario("invalid fresh stopped evidence", [i] {
        stub::f.after_install = [i] {
            auto& s = stub::f.status;
            switch (i) {
            case 0: s.state = TWAI_STATE_RUNNING; break;
            case 1: s.msgs_to_tx = 1; break;
            case 2: s.msgs_to_rx = 1; break;
            case 3: s.rx_missed_count = 1; break;
            case 4: s.rx_overrun_count = 1; break;
            case 5: s.tx_failed_count = 1; break;
            case 6: s.bus_error_count = 1; break;
            case 7: s.arb_lost_count = 1; break;
            case 8: stub::f.alerts = TWAI_ALERT_TX_IDLE; break;
            }
        };
        IdfTwaiPort p; CHECK(!p.reset_and_start()); CHECK(stub::f.call_count["start"] == 0);
        assert_failed_latch(p); const auto c = p.close(); CHECK(!c.healthy);
    });
    for (unsigned i = 0; i < 3; ++i) scenario("invalid post-start state", [i] {
        stub::f.after_start = [i] {
            if (i == 0) stub::f.status.state = TWAI_STATE_BUS_OFF;
            if (i == 1) stub::f.status.msgs_to_tx = 1;
            if (i == 2) stub::f.status.rx_missed_count = 1;
        };
        IdfTwaiPort p; CHECK(!p.reset_and_start()); assert_failed_latch(p);
        CHECK(p.close().quiesced);
    });
    for (unsigned i = 0; i < 2; ++i) scenario("old stop result invalid", [i] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.after_stop = [i] {
            if (i == 0) stub::f.status.state = TWAI_STATE_RUNNING;
            else stub::f.status.msgs_to_tx = 1;
        };
        CHECK(!p.reset_and_start()); CHECK(stub::f.call_count["install"] == 1);
        assert_failed_latch(p);
        stub::f.after_stop = {}; CHECK(p.close().quiesced);
    });
}

void close_evidence() {
    const std::uint32_t terminal_or_bad[] = {TWAI_ALERT_TX_SUCCESS, TWAI_ALERT_TX_FAILED,
        TWAI_ALERT_BUS_OFF, TWAI_ALERT_RX_QUEUE_FULL, TWAI_ALERT_RX_FIFO_OVERRUN,
        TWAI_ALERT_ERR_PASS, TWAI_ALERT_PERIPH_RESET, TWAI_ALERT_TX_RETRIED,
        TWAI_ALERT_BUS_ERROR, TWAI_ALERT_ABOVE_ERR_WARN, TWAI_ALERT_ARB_LOST, 0x80000000u};
    for (auto bit : terminal_or_bad) scenario("late alert at stop is retained", [bit] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.after_stop = [bit] { stub::f.alerts |= bit; };
        auto c = p.close(); CHECK(c.quiesced && !c.healthy);
        CHECK(!stub::f.installed); assert_failed_latch(p);
    });
    scenario("idle alone is healthy at close", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.after_stop = [] { stub::f.alerts = TWAI_ALERT_TX_IDLE; };
        auto c = p.close(); CHECK(c.quiesced && c.healthy);
    });
    for (unsigned i = 0; i < 7; ++i) scenario("late queue or counter at close", [i] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.after_stop = [i] {
            auto& s = stub::f.status;
            switch (i) {
            case 0: s.msgs_to_tx = 1; break;
            case 1: s.msgs_to_rx = 1; break;
            case 2: s.rx_missed_count = 1; break;
            case 3: s.rx_overrun_count = 1; break;
            case 4: s.tx_failed_count = 1; break;
            case 5: s.bus_error_count = 1; break;
            case 6: s.arb_lost_count = 1; break;
            }
        };
        const auto c = p.close(); CHECK(c.quiesced && !c.healthy);
    });
    scenario("stop clearing pending tx does not erase unhealthy evidence", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.status.msgs_to_tx = 1;
        const auto c = p.close(); CHECK(c.quiesced && !c.healthy);
    });
    for (auto state : {TWAI_STATE_STOPPED, TWAI_STATE_BUS_OFF, TWAI_STATE_RECOVERING})
        scenario("close initial state", [state] {
            IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.status.state = state;
            const auto c = p.close(); CHECK(c.quiesced == (state != TWAI_STATE_RECOVERING));
            CHECK(c.healthy == (state == TWAI_STATE_STOPPED));
            CHECK(stub::f.call_count["stop"] == 0);
        });
    for (auto state : {TWAI_STATE_RUNNING, TWAI_STATE_BUS_OFF, TWAI_STATE_RECOVERING})
        scenario("state changes at close boundary", [state] {
            IdfTwaiPort p; CHECK(p.reset_and_start());
            stub::f.after_stop = [state] { stub::f.status.state = state; };
            const auto c = p.close(); CHECK(!c.healthy);
            CHECK(c.quiesced == (state == TWAI_STATE_BUS_OFF));
        });
    const char* operations[] = {"status", "stop", "alerts", "uninstall"};
    for (auto op : operations) scenario("close API failure", [op] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::fail_next(op);
        const auto c = p.close(); CHECK(!c.healthy);
        CHECK(c.quiesced == (std::string(op) == "alerts"));
        assert_failed_latch(p);
        const auto count = stub::f.calls.size(); (void)p.close();
        CHECK(stub::f.calls.size() == count);
    });
    scenario("final status API failure", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        stub::f.fail_operation = "status"; stub::f.fail_occurrence = 4;
        auto c = p.close(); CHECK(!c.quiesced && !c.healthy);
        CHECK(stub::f.call_count["uninstall"] == 0);
    });
}

void io_contract() {
    scenario("all native alerts map to distinct abstraction bits", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        CHECK(stub::f.general.alerts_enabled == 0x1FF83u);
        const std::uint32_t native[] = {TWAI_ALERT_TX_SUCCESS, TWAI_ALERT_TX_FAILED,
            TWAI_ALERT_TX_IDLE, TWAI_ALERT_BUS_OFF, TWAI_ALERT_RX_QUEUE_FULL,
            TWAI_ALERT_RX_FIFO_OVERRUN, TWAI_ALERT_ERR_PASS, TWAI_ALERT_PERIPH_RESET,
            TWAI_ALERT_TX_RETRIED, TWAI_ALERT_BUS_ERROR, TWAI_ALERT_ABOVE_ERR_WARN,
            TWAI_ALERT_ARB_LOST};
        for (unsigned i = 0; i < 12; ++i) {
            stub::f.alerts = native[i]; std::uint32_t out = 0;
            CHECK(p.read_alerts(out)); CHECK(out == (1u << i));
        }
        stub::f.alerts = stub::f.general.alerts_enabled;
        std::uint32_t out = 0; CHECK(p.read_alerts(out)); CHECK(out == robot_can::all_alerts);
        CHECK(stub::f.alerts_wait == 0);
        CHECK(p.read_alerts(out) && out == 0); // ESP_ERR_TIMEOUT
        stub::f.empty_alert_success = true;
        CHECK(p.read_alerts(out) && out == 0); // stale semaphore / ESP_OK, zero
        CHECK(p.close().quiesced);
    });
    scenario("unexpected native alert fails closed", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.alerts = 0x80000000;
        std::uint32_t out = 9; CHECK(!p.read_alerts(out) && out == 0);
        assert_failed_latch(p); CHECK(p.close().quiesced);
    });
    scenario("all status fields and states preserved", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        auto& s = stub::f.status;
        s.msgs_to_tx=1; s.msgs_to_rx=2; s.rx_missed_count=3; s.rx_overrun_count=4;
        s.tx_failed_count=5; s.bus_error_count=6; s.arb_lost_count=7;
        const twai_state_t raw[] = {TWAI_STATE_STOPPED,TWAI_STATE_RUNNING,TWAI_STATE_BUS_OFF,TWAI_STATE_RECOVERING};
        const robot_can::BusState expected[] = {robot_can::BusState::Stopped,robot_can::BusState::Running,
            robot_can::BusState::BusOff,robot_can::BusState::Recovering};
        for (unsigned i=0;i<4;++i) {
            s.state=raw[i]; PortStatus out; CHECK(p.status(out)); CHECK(out.state==expected[i]);
            CHECK(out.tx_pending==1 && out.rx_pending==2 && out.rx_missed==3 && out.rx_overrun==4);
            CHECK(out.tx_failed==5 && out.bus_errors==6 && out.arbitration_lost==7);
        }
        s.state=TWAI_STATE_BUS_OFF; CHECK(p.close().quiesced);
    });
    for (const auto op : {"alerts", "status", "receive", "transmit"})
        scenario("I/O failure latches but cleanup remains available", [op] {
            IdfTwaiPort p; CHECK(p.reset_and_start()); stub::fail_next(op);
            std::uint32_t alerts=0; PortStatus status; RxFrame rx;
            if (std::string(op)=="alerts") CHECK(!p.read_alerts(alerts));
            if (std::string(op)=="status") CHECK(!p.status(status));
            if (std::string(op)=="receive") CHECK(p.receive(rx)==ReceiveResult::Error);
            if (std::string(op)=="transmit") CHECK(!p.submit(WireFrame{1,2,{0xF7,0xF8}},100));
            assert_failed_latch(p); const auto c=p.close(); CHECK(c.quiesced && !c.healthy);
        });
    scenario("receive preserves untrusted ID DLC flags and dequeue time", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); RxFrame out;
        CHECK(p.receive(out)==ReceiveResult::Empty && stub::f.rx_wait==0);
        twai_message_t message{}; message.identifier=0x1FFFFFFF; message.data_length_code=9;
        message.extd=1; message.rtr=1;
        for (unsigned i=0;i<8;++i) message.data[i]=static_cast<std::uint8_t>(i+1);
        stub::f.rx.push_back(message); stub::f.status.msgs_to_rx=1;
        stub::f.micros=1999; stub::f.after_receive=[] { stub::f.micros=2345; };
        CHECK(p.receive(out)==ReceiveResult::Data);
        CHECK(out.frame.id==0x1FFFFFFF && out.frame.dlc==9 && out.frame.extended && out.frame.rtr);
        CHECK(out.dequeued_at==2 && out.frame.data[7]==8 && stub::f.rx_wait==0);
        CHECK(p.close().quiesced);
    });
    scenario("negative clock cannot create a valid RX timestamp", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.micros=-1;
        CHECK(p.now_ms()==std::numeric_limits<std::uint64_t>::max());
        stub::f.rx.push_back({}); RxFrame out;
        CHECK(p.receive(out)==ReceiveResult::Error); assert_failed_latch(p);
        CHECK(p.close().quiesced);
    });
    scenario("single shot standard zero wait transmit only accepts", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start());
        const WireFrame frame{2, 8, {0xFD,0,5,2,0,0,100,0x6A}};
        CHECK(p.submit(frame,50));
        CHECK(stub::f.sent.identifier==2 && stub::f.sent.data_length_code==8);
        CHECK(stub::f.sent.ss==1 && stub::f.sent.extd==0 && stub::f.sent.rtr==0);
        CHECK(stub::f.sent.self==0 && stub::f.sent.dlc_non_comp==0 && stub::f.sent.reserved==0);
        CHECK(stub::f.sent.data[7]==0x6A && stub::f.tx_wait==0);
        std::uint32_t alerts=7; CHECK(p.read_alerts(alerts) && alerts==0);
        PortStatus out; CHECK(p.status(out) && out.tx_pending==1);
        CHECK(!p.submit(frame,50)); // No hidden SW queue or retry.
        CHECK(stub::f.call_count["transmit"]==2); assert_failed_latch(p);
        CHECK(p.close().quiesced);
    });
    for (unsigned i=0;i<4;++i) scenario("bad outbound frame never reaches SDK", [i] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); WireFrame frame{1,2,{0xF7,0xF8}};
        if(i==0)frame.id=0x800; if(i==1)frame.dlc=9;
        if(i==2)frame.extended=true; if(i==3)frame.rtr=true;
        CHECK(!p.submit(frame,50)); CHECK(stub::f.call_count["transmit"]==0);
        assert_failed_latch(p); CHECK(p.close().quiesced);
    });
    scenario("deadline equality prevents submission", [] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.micros=50000;
        CHECK(!p.submit(WireFrame{1,2,{0xF7,0xF8}},50));
        CHECK(stub::f.call_count["transmit"]==0); assert_failed_latch(p); CHECK(p.close().quiesced);
    });
    for (bool backwards : {false,true}) scenario("late or reversed SDK return is not acceptance", [backwards] {
        IdfTwaiPort p; CHECK(p.reset_and_start()); stub::f.micros=10000;
        stub::f.after_transmit=[backwards] { stub::f.micros=backwards ? 9000 : 50000; };
        CHECK(!p.submit(WireFrame{1,2,{0xF7,0xF8}},50));
        CHECK(stub::f.call_count["transmit"]==1); assert_failed_latch(p);
        const auto c=p.close(); CHECK(c.quiesced && !c.healthy);
    });
}
} // namespace

int main() {
    basic_configuration(); lifecycle_failures(); close_evidence(); io_contract();
    std::cout << "TWAI_SDK_STUB_PASS cases=" << cases << " assertions=" << assertions << '\n';
    return 0;
}
