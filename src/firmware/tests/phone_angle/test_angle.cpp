#define ROBOT_BOOT_FIXTURE_ONLY
#include "../boot/test_boot.cpp"
#include "robot_phone/owner.hpp"
#include <string>
#include <iostream>
#include <cstring>
namespace phone=robot_phone;
phone::Secret secret(char c){phone::Secret x{};for(unsigned i=0;i<32;++i)x[i]=c;return x;}
phone::Seed seed(){phone::Seed s;s.boot=11;s.pairing=secret('a');s.credentials={secret('b'),secret('c')};s.principals={101,202};return s;}
struct AngleFixture {
 BootFake p;robot_boot::Profile profile;std::array<robot_joint::Calibration,2> calibration;phone::Owner owner;
 phone::Secret credential{};Time seq{0},job{0},lease{0},ticket{0},renewed{0};bool renewing{false};unsigned axis;
 static std::array<robot_joint::Calibration,2> maps(bool measured){return {{{measured,robot_joint::Layout::FixedV2_025,11,22,1,1,200,16,27.,1},{measured,robot_joint::Layout::FixedV2_025,11,22,2,2,200,16,9.,-1}}};}
 explicit AngleFixture(unsigned selected=1,bool measured=true):profile(boot_profile(selected)),calibration(maps(measured)),owner(p,profile,seed(),calibration),axis(selected){owner.begin();phone::Envelope e;e.pairing=true;e.credential=seed().pairing;const auto r=transact(e);CHECK(r.paired);credential=r.credential;}
 phone::Result transact(phone::Envelope e){e.job=++job;e.enqueued_at=p.now;CHECK(owner.enqueue(e));owner.tick();phone::Result r;for(unsigned i=0;i<50;++i){if(owner.take_result(e.listener,e.job,r))return r;++p.now;owner.tick();}CHECK(false);return r;}
 phone::Result wire(phone::Wire w){phone::Envelope e;e.listener=w.op==phone::Op::Stop?phone::Listener::Stop:phone::Listener::Normal;e.credential=credential;e.wire=w;return transact(e);}
 phone::Wire message(phone::Op op){phone::Wire w;w.boot=11;w.phase=owner.snapshot().generation;w.seq=w.request=++seq;w.op=op;w.lease=lease;w.ticket=ticket;w.axis=static_cast<std::uint16_t>(axis);w.unloaded=true;return w;}
 phone::Result command(phone::Op op){const auto r=wire(message(op));if(r.error==phone::Error::None){if(r.lease)lease=r.lease;if(r.ticket)ticket=r.ticket;}return r;}
 void accepted(phone::Op op){const auto r=command(op);CHECK(r.error==phone::Error::None);}
 void step(){++p.now;if(p.wire.data[0]==0xFD)p.movement_delta=(p.wire.data[1]&0x80)?-3200:3200;owner.tick();if(renewing&&p.now-renewed>=200&&owner.snapshot().phase!=phone::Phase::Stopping&&owner.snapshot().phase!=phone::Phase::Terminal){renewed=p.now;accepted(owner.snapshot().phase==phone::Phase::Boot?phone::Op::MaintenanceRenew:phone::Op::Renew);}}
 void delay(unsigned n){while(n--)step();}
 void state(unsigned desired,unsigned limit=3000){for(unsigned i=0;i<limit&&owner.snapshot().core_state!=desired&&owner.snapshot().phase!=phone::Phase::Terminal;++i)step();CHECK(owner.snapshot().core_state==desired);}
 void bootstrap(){state(static_cast<unsigned>(robot_boot::State::NeedsMaintenance));accepted(phone::Op::Maintenance);renewing=true;renewed=p.now;accepted(phone::Op::Unloaded);accepted(phone::Op::DisableAll);state(static_cast<unsigned>(robot_boot::State::ReadyDisabled));accepted(phone::Op::FinishMaintenance);lease=0;accepted(phone::Op::Drive);accepted(phone::Op::EnableSelected);state(static_cast<unsigned>(robot_boot::State::Granted));delay(600);renewing=false;accepted(phone::Op::Handoff);lease=ticket=seq=0;state(static_cast<unsigned>(robot_run::State::Ready));seq=0;}
 void favorable(){for(unsigned n=0;n<40&&(p.ps.tx_pending||p.size);++n)step();}
 void permit(){accepted(phone::Op::Acquire);renewing=true;renewed=p.now;for(unsigned n=0;n<10;++n){favorable();const auto r=command(phone::Op::Arm);if(r.error==phone::Error::None)break;CHECK(r.core_error==static_cast<unsigned>(robot_gate::Error::Busy));delay(101);}accepted(phone::Op::Ticket);}
 std::string body(std::string angle,std::string unit="deg",unsigned joint=0){const auto w=message(phone::Op::JointStep);return "v2|11|"+std::to_string(w.phase)+"|"+std::to_string(w.seq)+"|"+std::to_string(w.request)+"|joint-step|"+std::to_string(lease)+"|"+std::to_string(ticket)+"|"+std::to_string(axis)+"|"+std::to_string(joint?joint:axis)+"|"+unit+"|"+angle;}
 phone::Result angle(std::string value,std::string unit="deg",unsigned joint=0){phone::Wire w;CHECK(phone::parse(body(value,unit,joint),w));return wire(w);}
};
static void parsing(){
 const std::string prefix="v2|11|2|3|3|joint-step|4|5|1|1|deg|";
 for(const char* s:{"0.4166666666666667","-0.4166666666666667","999999.999999999999999999","0.000000000000000001"}){phone::Wire w;CHECK(phone::parse(prefix+s,w));CHECK(w.op==phone::Op::JointStep&&w.joint==1&&std::isfinite(w.angle));}
 for(const char* s:{"","0","-0","0.0","+1","01","1.",".5","1e2","nan","NaN","Infinity","1,2"," 1","1 ","1000000","1.0000000000000000000","1|0","--1"}){phone::Wire w;CHECK(!phone::parse(prefix+s,w));}
 for(const char* s:{"v2|11|2|3|3|move|4|5|1|1|deg|1","v2|11|2|3|3|joint-step|4|5|0|1|deg|1","v2|11|2|3|3|joint-step|4|5|1|7|deg|1","v2|11|2|3|3|joint-step|4|5|1|1|DEG|1","v1|11|2|3|3|joint-step|4|5|1|0|0"}){phone::Wire w;CHECK(!phone::parse(s,w));}
}
static void production_paths(){
 for(unsigned axis:{1u,2u})for(bool negative:{false,true})for(bool radians:{false,true}){
  AngleFixture f(axis);f.bootstrap();CHECK(f.owner.snapshot().angle_available&&f.owner.snapshot().angle_joint==axis);f.permit();
  std::string value=axis==1?(radians?"0.00727220521664304":"0.4166666666666667"):(radians?"0.02181661564992912":"1.25");if(negative)value="-"+value;
  CHECK(f.angle(value,radians?"rad":"deg").error==phone::Error::None);CHECK(f.p.moves==1);
  const bool dir1=negative!=(axis==2);unsigned sent=0;for(unsigned i=0;i<f.p.sent_count;++i)if(f.p.sent[i].frame.data[0]==0xFD){++sent;CHECK(f.p.sent[i].frame.id==axis);CHECK((f.p.sent[i].frame.data[1]&0x80)==(dir1?0x80:0));CHECK(f.p.sent[i].frame.data[6]==100);}
  CHECK(sent==1);CHECK(!f.owner.snapshot().ready&&f.owner.snapshot().angle_available);
  f.state(static_cast<unsigned>(robot_run::State::Ready));CHECK(f.owner.snapshot().angle_available);f.accepted(phone::Op::Stop);f.renewing=false;f.state(static_cast<unsigned>(robot_run::State::StoppedRecheck),3600);CHECK(f.owner.snapshot().stop_verified);
 }
 {AngleFixture f(1,false);f.bootstrap();CHECK(!f.owner.snapshot().angle_available);f.permit();CHECK(f.angle("0.4166666666666667").error!=phone::Error::None);f.step();CHECK(f.p.moves==0);}
 for(unsigned failure=0;failure<6;++failure){AngleFixture f;f.bootstrap();f.permit();phone::Wire w;CHECK(phone::parse(f.body("0.4166666666666667"),w));
  switch(failure){case 0:++w.phase;break;case 1:++w.lease;break;case 2:++w.ticket;break;case 3:w.joint=2;break;case 4:w.axis=2;break;default:w.angle=1.;break;}
  CHECK(f.wire(w).error!=phone::Error::None);f.step();CHECK(f.p.moves==0);
 }
 {AngleFixture f;f.bootstrap();f.permit();f.owner.revoke_joint_mapping();CHECK(!f.owner.snapshot().angle_available);const auto first=f.owner.snapshot();CHECK(f.angle("0.4166666666666667").error!=phone::Error::None);CHECK(f.p.moves==0);CHECK(f.owner.snapshot().fault_at==first.fault_at);}
 {AngleFixture f;f.bootstrap();f.permit();phone::Envelope angle;angle.listener=phone::Listener::Normal;angle.credential=f.credential;angle.job=++f.job;angle.enqueued_at=f.p.now;CHECK(phone::parse(f.body("0.4166666666666667"),angle.wire));CHECK(f.owner.enqueue(angle));phone::Envelope stop;stop.listener=phone::Listener::Stop;stop.credential=f.credential;stop.job=++f.job;stop.enqueued_at=f.p.now;stop.wire=f.message(phone::Op::Stop);CHECK(f.owner.enqueue(stop));f.owner.tick();CHECK(f.p.moves==0);}
}
static void status(AngleFixture& f){const auto s=f.owner.snapshot();std::cout<<"{\"boot\":\"11\",\"generation\":\""<<s.generation<<"\",\"at\":\""<<s.at<<"\",\"lease_owner\":\""<<s.lease_owner<<"\",\"lease_until\":\""<<s.lease_until<<"\",\"config_oldest_at\":\""<<s.config_oldest_at<<"\",\"fault_at\":\""<<s.fault_at<<"\",\"stop_at\":\""<<s.stop_at<<"\",\"phase\":"<<unsigned(s.phase)<<",\"core_state\":"<<s.core_state<<",\"core_fault\":"<<s.core_fault<<",\"ready\":"<<(s.ready?"true":"false")<<",\"selected_axis\":"<<s.selected_axis<<",\"angle_available\":"<<(s.angle_available?"true":"false")<<",\"angle_joint\":"<<s.angle_joint<<"}"<<std::endl;}
static void bridge(unsigned axis,bool measured){AngleFixture f(axis,measured);f.bootstrap();std::string line;while(std::getline(std::cin,line)){
 if(line=="S"){status(f);continue;}if(line.rfind("T ",0)==0){f.delay(static_cast<unsigned>(std::stoul(line.substr(2))));std::cout<<"{}"<<std::endl;continue;}
 if(line=="R"){f.owner.revoke_joint_mapping();std::cout<<"{}"<<std::endl;continue;}
 if(line=="M"){std::cout<<"{\"moves\":"<<f.p.moves<<",\"violations\":"<<f.p.violations<<"}"<<std::endl;continue;}
 if(line.rfind("C ",0)==0){phone::Wire w;if(!phone::parse(line.substr(2),w)){std::cout<<"{\"wire_error\":1,\"core_error\":0}"<<std::endl;continue;}f.favorable();const auto r=f.wire(w);std::cout<<"{\"wire_error\":"<<unsigned(r.error)<<",\"core_error\":"<<r.core_error<<",\"lease\":\""<<r.lease<<"\",\"ticket\":\""<<r.ticket<<"\",\"accepted_at\":\""<<r.accepted_at<<"\"}"<<std::endl;continue;}
 std::cout<<"{}"<<std::endl;
}}
int main(int argc,char** argv){if(argc==4&&std::strcmp(argv[1],"--bridge")==0){bridge(static_cast<unsigned>(std::stoul(argv[2])),std::strcmp(argv[3],"true")==0);return 0;}parsing();production_paths();std::printf("ANGLE PASS assertions=%u actual=parse->Owner->Boot/Run->Gate->codec->FakeCAN hardware=NOT_RUN\n",assertions);return 0;}
