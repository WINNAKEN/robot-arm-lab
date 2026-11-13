#include "robot_diagnostic/diagnostic.hpp"
#include "robot_diagnostic/execution.hpp"
#include <vector>
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace robot_diagnostic;
using namespace robot_can;
namespace {
unsigned assertions=0,scenarios=0;
#define CHECK(x) do { ++assertions;if(!(x)){std::fprintf(stderr,"CHECK FAILED: %s:%d %s\n",__FILE__,__LINE__,#x);std::exit(1);} }while(false)
WireFrame response(std::uint16_t axis,std::uint8_t code,std::int64_t value){
    WireFrame f{};f.id=axis;f.data[0]=code;const unsigned bytes=code==0x31?6:code==0x32?2:1;f.dlc=static_cast<std::uint8_t>(bytes+2);
    const auto bits=static_cast<std::uint64_t>(value);
    for(unsigned j=0;j<bytes;++j)f.data[1+j]=static_cast<std::uint8_t>((bits>>(8*(bytes-j-1)))&255u);
    unsigned sum=axis;for(unsigned j=0;j+1<f.dlc;++j)sum+=f.data[j];f.data[f.dlc-1]=static_cast<std::uint8_t>(sum&255u);return f;
}
struct Fake final:CanPort{
    std::uint64_t t{1000};mutable unsigned calls{0};unsigned reset_calls{0},close_calls{0};
    unsigned reset_delay{0},submit_delay{0},receive_delay{0},close_delay{0};
    bool reset_ok{true},submit_ok{true},alerts_ok{true},status_ok{true},receive_ok{true};
    bool auto_tx{true},auto_rx{true},close_q{true},close_h{true},started{false},scheduled{false},sent_tx{false},sent_rx{false};
    std::uint64_t sent_at{0};std::uint32_t alerts{0};PortStatus extra{};std::vector<WireFrame> sent;std::vector<RxFrame> queue;
    std::int64_t enable{0},run_state{1},position{-1},speed{-123};
    std::uint64_t now_ms()const noexcept override{++calls;return t;}
    void ready(){
        if(!scheduled)return;
        if(auto_tx && !sent_tx && t>=sent_at+1){alerts|=TxSuccess;sent_tx=true;}
        if(auto_rx && !sent_rx && t>=sent_at+2){const auto& f=sent.back();const auto c=f.data[0];queue.push_back({response(static_cast<std::uint16_t>(f.id),c,c==0x3A?enable:c==0xF1?run_state:c==0x31?position:speed),t});sent_rx=true;}
    }
    bool reset_and_start()noexcept override{++calls;++reset_calls;t+=reset_delay;started=true;return reset_ok;}
    CloseResult close()noexcept override{++calls;++close_calls;t+=close_delay;started=false;return {close_q,close_h};}
    bool read_alerts(std::uint32_t& a)noexcept override{++calls;ready();a=alerts;alerts=0;return alerts_ok;}
    bool status(PortStatus& s)noexcept override{++calls;ready();s=extra;s.state=started?BusState::Running:BusState::Stopped;if(extra.state==BusState::BusOff||extra.state==BusState::Recovering)s.state=extra.state;s.rx_pending=static_cast<std::uint32_t>(queue.size())+extra.rx_pending;s.tx_pending=(scheduled&&!sent_tx?1u:0u)+extra.tx_pending;return status_ok;}
    ReceiveResult receive(RxFrame& r)noexcept override{++calls;t+=receive_delay;ready();if(!receive_ok)return ReceiveResult::Error;if(queue.empty())return ReceiveResult::Empty;r=queue.front();queue.erase(queue.begin());return ReceiveResult::Data;}
    bool submit(const WireFrame& f,std::uint64_t before)noexcept override{++calls;CHECK(t<before);sent.push_back(f);t+=submit_delay;sent_at=t;scheduled=true;sent_tx=sent_rx=false;return submit_ok;}
};
Profile approved(std::uint16_t axis=1){Profile p{};p.axis=axis;p.board_confirmed=p.can_protocol_confirmed=p.bitrate_confirmed=p.no_power_on_motion_confirmed=p.hardware_approved=true;return p;}
void run(Runner& r,Fake& p,unsigned duration=3000){for(unsigned i=0;i<duration && !r.terminal();++i){r.poll();++p.t;}}
void until(Runner& r,Fake& p,std::uint64_t target){while(p.t<target && !r.terminal()){++p.t;r.poll();}}
void default_and_allowlist(){
    ++scenarios;Fake p;Runner r(p);CHECK(p.calls==0);CHECK(!r.begin(Profile{}));CHECK(p.calls==0);CHECK(r.state()==State::Rejected);r.poll();CHECK(p.calls==0);
    for(unsigned which=0;which<5;++which){++scenarios;Fake f;Runner x(f);auto profile=approved();switch(which){case 0:profile.board_confirmed=false;break;case 1:profile.can_protocol_confirmed=false;break;case 2:profile.bitrate_confirmed=false;break;case 3:profile.no_power_on_motion_confirmed=false;break;default:profile.hardware_approved=false;}CHECK(!x.begin(profile));CHECK(f.calls==0);}
    for(const auto axis:{0,3,2047}){++scenarios;Fake f;Runner x(f);CHECK(!x.begin(approved(static_cast<std::uint16_t>(axis))));CHECK(f.calls==0);}
    ++scenarios;
    for(unsigned axis=1;axis<=2;++axis)for(unsigned code=0;code<256;++code){WireFrame f{};f.id=axis;f.dlc=2;f.data[0]=static_cast<std::uint8_t>(code);f.data[1]=static_cast<std::uint8_t>((axis+code)&255u);CHECK(is_read_request(f,static_cast<std::uint16_t>(axis))==(code==0x31||code==0x32||code==0xF1||code==0x3A));}
    WireFrame f{};f.id=2;f.dlc=2;f.data[0]=0xF1;f.data[1]=0xF3;CHECK(is_read_request(f,2));
    auto wrong=f;wrong.rtr=true;CHECK(!is_read_request(wrong,2));wrong=f;wrong.extended=true;CHECK(!is_read_request(wrong,2));wrong=f;wrong.id=0x10002;CHECK(!is_read_request(wrong,2));wrong=f;wrong.dlc=3;CHECK(!is_read_request(wrong,2));wrong=f;wrong.data[1]^=1;CHECK(!is_read_request(wrong,2));wrong=f;wrong.data[7]=1;CHECK(!is_read_request(wrong,2));
}
void positive(){
 for(unsigned axis=1;axis<=2;++axis){++scenarios;Fake p;Runner r(p);auto profile=approved(static_cast<std::uint16_t>(axis));CHECK(r.begin(profile));CHECK(p.sent.empty());profile.axis=3;CHECK(!r.begin(profile));run(r,p);CHECK(r.state()==State::Complete);CHECK(r.error()==Error::None);CHECK(p.sent.size()==4);CHECK(p.reset_calls==1&&p.close_calls==1);const std::uint8_t opcodes[]={0x3A,0xF1,0x31,0x32};for(unsigned i=0;i<4;++i){CHECK(p.sent[i].data[0]==opcodes[i]);CHECK(is_read_request(p.sent[i],static_cast<std::uint16_t>(axis)));CHECK(r.values_seen()[i]);}CHECK(r.values()[0]==0&&r.values()[1]==1&&r.values()[2]==-1&&r.values()[3]==-123);const auto calls=p.calls;for(unsigned i=0;i<20;++i)r.poll();CHECK(p.calls==calls);CHECK(!r.begin(approved()));CHECK(p.calls==calls);CHECK(!r.journal_overflow());
 }
}
void profile_and_open(){
 for(const auto limit:{0u,129u}){++scenarios;Fake p;Runner r(p);auto a=approved();a.record_limit=limit;CHECK(!r.begin(a));CHECK(p.calls==0);}
 for(const auto delay:{99u,100u}){++scenarios;Fake p;p.reset_delay=delay;Runner r(p);CHECK(r.begin(approved())==(delay==99));if(delay==100)CHECK(r.state()==State::Fault&&p.close_calls==1);}
 for(unsigned kind=0;kind<5;++kind){++scenarios;Fake p;if(kind==0)p.reset_ok=false;if(kind==1)p.alerts=TxIdle;if(kind==2)p.queue.push_back({response(1,0x3A,0),p.t});if(kind==3)p.extra.rx_missed=1;if(kind==4)p.extra.tx_pending=1;Runner r(p);CHECK(!r.begin(approved()));CHECK(p.close_calls==1);CHECK(p.sent.empty());}
 ++scenarios;Fake p;p.t=std::numeric_limits<std::uint64_t>::max()-100;Runner r(p);CHECK(!r.begin(approved()));CHECK(p.reset_calls==0);
}
void errors_and_close(){
 for(unsigned mode=0;mode<15;++mode){++scenarios;Fake p;Runner r(p);CHECK(r.begin(approved()));switch(mode){case 0:p.alerts=BusOff;break;case 1:p.alerts=TxFailed;break;case 2:p.alerts=TxSuccess;break;case 3:p.alerts=1u<<31;break;case 4:p.extra.bus_errors=1;break;case 5:p.extra.rx_overrun=1;break;case 6:p.alerts_ok=false;break;case 7:p.status_ok=false;break;case 8:p.receive_ok=false;break;case 9:p.extra.state=BusState::BusOff;break;case 10:p.extra.state=BusState::Recovering;break;case 11:p.submit_ok=false;break;case 12:p.extra.tx_pending=2;break;case 13:p.extra.arbitration_lost=1;break;default:p.extra.tx_failed=1;}
 run(r,p);CHECK(r.state()==State::Fault);CHECK(p.close_calls==1);const auto n=p.calls;r.poll();CHECK(p.calls==n);for(const auto& f:p.sent)CHECK(is_read_request(f,1));}
 for(unsigned mode=0;mode<3;++mode){++scenarios;Fake p;if(mode==0)p.close_q=false;if(mode==1)p.close_h=false;if(mode==2)p.close_delay=10;Runner r(p);CHECK(r.begin(approved()));run(r,p);CHECK(r.state()==State::Fault);CHECK(p.sent.size()==4);CHECK(p.close_calls==1);CHECK(r.error()==(mode==2?Error::Service:Error::Close));}
 ++scenarios;Fake p;Runner r(p);auto a=approved();a.record_limit=4;CHECK(r.begin(a));run(r,p);CHECK(r.state()==State::Fault&&r.journal_overflow());CHECK(p.close_calls==1);CHECK(r.event_count()==4);
}
void time_limits(){
 for(const auto gap:{9u,10u}){++scenarios;Fake p;Runner r(p);CHECK(r.begin(approved()));p.t+=gap;r.poll();CHECK((r.state()==State::Fault)==(gap==10));}
 for(const auto delay:{9u,10u}){++scenarios;Fake p;p.submit_delay=delay;Runner r(p);CHECK(r.begin(approved()));r.poll();CHECK((r.state()==State::Fault)==(delay==10));CHECK(p.sent.size()==1);}
 ++scenarios;Fake p;Runner r(p);CHECK(r.begin(approved()));--p.t;r.poll();CHECK(r.error()==Error::Clock&&p.close_calls==1);
 ++scenarios;Fake q;Runner s(q);CHECK(s.begin(approved()));q.receive_delay=10;s.poll();CHECK(s.error()==Error::Service);
 for(const auto at:{249u,250u}){++scenarios;Fake f;f.auto_tx=f.auto_rx=false;Runner x(f);CHECK(x.begin(approved()));x.poll();const auto origin=f.sent_at;until(x,f,origin+at-1);f.sent_tx=true;f.alerts|=TxSuccess;++f.t;x.poll();CHECK((x.state()==State::Fault)==(at==250));if(at==249)CHECK(x.state()==State::AwaitRx);}
 for(const auto at:{499u,500u}){++scenarios;Fake f;f.auto_rx=false;Runner x(f);CHECK(x.begin(approved()));x.poll();const auto origin=f.sent_at;until(x,f,origin+at-1);f.queue.push_back({response(1,0x3A,0),origin+at});++f.t;x.poll();CHECK((x.state()==State::Fault)==(at==500));if(at==499)CHECK(x.values_seen()[0]);}
}
void receive_rejections(){
 for(unsigned mode=0;mode<12;++mode){++scenarios;Fake p;p.auto_rx=false;Runner r(p);CHECK(r.begin(approved()));r.poll();++p.t;r.poll();CHECK(r.state()==State::AwaitRx);auto f=response(1,0x3A,0);std::uint64_t stamp=p.t+1;
 switch(mode){case 0:f.id=2;break;case 1:f.id=0x10001;break;case 2:f.extended=true;break;case 3:f.rtr=true;break;case 4:f.dlc=9;break;case 5:f.data[2]^=1;break;case 6:f=response(1,0xF1,1);break;case 7:stamp=0;break;case 8:stamp=999;break;case 9:stamp=p.t+100;break;case 10:f.dlc=2;break;default:p.queue.push_back({f,stamp});}
 p.queue.push_back({f,stamp});++p.t;r.poll();CHECK(r.state()==State::Fault);CHECK(p.close_calls==1);bool raw=false;for(std::size_t i=0;i<r.event_count();++i)raw|=r.event(i).kind==Kind::RxRaw;CHECK(raw);}
 ++scenarios;Fake p;p.auto_tx=false;Runner r(p);CHECK(r.begin(approved()));run(r,p);CHECK(r.error()==Error::UnexpectedRx);
 ++scenarios;Fake q;q.auto_rx=false;Runner s(q);CHECK(s.begin(approved()));q.queue.push_back({response(1,0x3A,0),q.t});s.poll();CHECK(s.error()==Error::UnexpectedRx&&q.sent.empty());
}
void device_states(){
 ++scenarios;Fake p;p.enable=1;Runner r(p);CHECK(r.begin(approved()));run(r,p);CHECK(r.error()==Error::Device&&p.sent.size()==1&&r.values()[0]==1);
 for(const auto status:{0,2,3,4,5,6}){++scenarios;Fake f;f.run_state=status;Runner x(f);CHECK(x.begin(approved()));run(x,f);CHECK(x.error()==Error::Device&&f.sent.size()==2&&x.values()[1]==status);}
}
Observed observed(){Observed o{};o.board=Board::WaveshareCanU;o.protocol=Protocol::MakerbaseCan;o.hardware_revision="CAN PCB observed fixture";o.firmware_version="V1.0.9 fixture";o.can_id=1;o.bitrate=500000;o.tx_gpio=15;o.rx_gpio=16;o.wiring=o.power_on_motion_excluded=Check::Pass;return o;}
void profile_preparation(){
 ++scenarios;const auto unknown=prepare_profile(Observed{},0);CHECK(unknown.readiness==Readiness::Pending&&unknown.missing==1023&&unknown.mismatch==0);CHECK(!unknown.transport.hardware_approved);Fake p;Runner r(p);CHECK(!r.begin(unknown.transport));CHECK(p.calls==0);
 ++scenarios;const auto valid=prepare_profile(observed(),1);CHECK(valid.readiness==Readiness::ReadyForReview&&valid.missing==0&&valid.mismatch==0);CHECK(!valid.transport.hardware_approved);Fake q;Runner s(q);CHECK(!s.begin(valid.transport));CHECK(q.calls==0);
 for(unsigned mode=0;mode<10;++mode){++scenarios;auto o=observed();std::uint32_t issue=0;switch(mode){case 0:o.board=Board::Unknown;issue=BoardIssue;break;case 1:o.protocol=Protocol::Unknown;issue=ProtocolIssue;break;case 2:o.hardware_revision="";issue=HardwareRecord;break;case 3:o.firmware_version="   ";issue=FirmwareRecord;break;case 4:o.can_id=0;issue=IdIssue;break;case 5:o.bitrate=0;issue=RateIssue;break;case 6:o.tx_gpio=-1;issue=PinIssue;break;case 7:o.rx_gpio=-1;issue=PinIssue;break;case 8:o.wiring=Check::Unknown;issue=WiringIssue;break;default:o.power_on_motion_excluded=Check::Unknown;issue=PowerOnIssue;}
 const auto a=prepare_profile(o,1);CHECK(a.readiness==Readiness::Pending);CHECK(a.missing==issue&&a.mismatch==0);CHECK(!a.transport.hardware_approved);}
 for(unsigned mode=0;mode<10;++mode){++scenarios;auto o=observed();std::uint32_t issue=0;switch(mode){case 0:o.board=Board::Other;issue=BoardIssue;break;case 1:o.protocol=Protocol::Rs485;issue=ProtocolIssue;break;case 2:o.hardware_revision="bad\nrecord";issue=HardwareRecord;break;case 3:o.firmware_version=std::string_view("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx");issue=FirmwareRecord;break;case 4:o.can_id=2;issue=IdIssue;break;case 5:o.bitrate=1000000;issue=RateIssue;break;case 6:o.tx_gpio=14;issue=PinIssue;break;case 7:o.rx_gpio=18;issue=PinIssue;break;case 8:o.wiring=Check::Fail;issue=WiringIssue;break;default:o.power_on_motion_excluded=Check::Fail;issue=PowerOnIssue;}
 const auto a=prepare_profile(o,1);CHECK(a.readiness==Readiness::Mismatch);CHECK((a.mismatch&issue)!=0);CHECK(!a.transport.hardware_approved);}
 ++scenarios;auto o=observed();o.tx_gpio=14;o.rx_gpio=-1;CHECK(prepare_profile(o,1).readiness==Readiness::Mismatch);CHECK((prepare_profile(o,0).missing&Selection)!=0);CHECK((prepare_profile(o,3).mismatch&Selection)!=0);o=observed();o.hardware_revision="SERVO42D_485";o.protocol=Protocol::Unknown;CHECK((prepare_profile(o,1).missing&ProtocolIssue)!=0);
}
void cadence_controls(){
 ++scenarios;Cadence c;CHECK(c.observe(100)==Due::ClockFault);CHECK(c.begin(100));CHECK(c.next_due()==100);CHECK(c.observe(100)==Due::Poll);CHECK(c.observe(100)==Due::Early);CHECK(c.observe(101)==Due::Poll);CHECK(!c.begin(101));CHECK(c.observe(101)==Due::Early);CHECK(c.observe(100)==Due::ClockFault);CHECK(c.observe(102)==Due::ClockFault);
 for(const auto gap:{9u,10u}){++scenarios;Cadence x;CHECK(x.begin(100));CHECK(x.observe(100)==Due::Poll);CHECK(x.observe(100+gap)==(gap==9?Due::Poll:Due::LateFault));if(gap==9){CHECK(x.next_due()==110);CHECK(x.observe(109)==Due::Early);}}
 ++scenarios;Cadence top;CHECK(!top.begin(std::numeric_limits<std::uint64_t>::max()));CHECK(top.observe(0)==Due::OverflowFault);Cadence edge;CHECK(edge.begin(std::numeric_limits<std::uint64_t>::max()-1));CHECK(edge.observe(std::numeric_limits<std::uint64_t>::max()-1)==Due::Poll);CHECK(edge.observe(std::numeric_limits<std::uint64_t>::max())==Due::OverflowFault);
 ++scenarios;Fake p;Runner r(p);Cadence active;CHECK(r.begin(approved()));CHECK(active.begin(r.schedule_now_ms()));service_scheduled_poll(r,active);CHECK(p.sent.size()==1);const auto calls=p.calls;service_scheduled_poll(r,active);CHECK(p.sent.size()==1&&p.calls==calls+1);for(unsigned i=0;i<3000&&!r.terminal();++i){++p.t;service_scheduled_poll(r,active);}CHECK(r.state()==State::Complete&&p.sent.size()==4);const auto closed=p.calls;service_scheduled_poll(r,active);schedule_wait_result(r,false);CHECK(r.schedule_now_ms()==0);CHECK(p.calls==closed);
 for(unsigned mode=0;mode<3;++mode){++scenarios;Fake f;Runner x(f);Cadence y;CHECK(x.begin(approved()));CHECK(y.begin(x.schedule_now_ms()));service_scheduled_poll(x,y);if(mode==0)f.t+=10;if(mode==1)--f.t;if(mode==2)schedule_wait_result(x,false);else service_scheduled_poll(x,y);CHECK(x.error()==Error::Schedule&&x.state()==State::Fault&&f.close_calls==1);CHECK(f.sent.size()==1&&is_read_request(f.sent[0],1));}
 ++scenarios;Fake idle;Runner inactive(idle);Cadence empty;service_scheduled_poll(inactive,empty);schedule_wait_result(inactive,false);inactive.abort_schedule();CHECK(inactive.schedule_now_ms()==0&&idle.calls==0);CHECK(!inactive.begin(Profile{}));service_scheduled_poll(inactive,empty);CHECK(idle.calls==0);
}
}
int main(){default_and_allowlist();positive();profile_and_open();errors_and_close();time_limits();receive_rejections();device_states();profile_preparation();cadence_controls();std::printf("DIAGNOSTIC_HOST_PASS scenarios=%u assertions=%u hardware=false\n",scenarios,assertions);return 0;}
