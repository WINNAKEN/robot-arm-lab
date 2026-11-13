#include "robot_run/bench_run.hpp"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace robot_run;using namespace robot_can;using robot_gate::Op;
static unsigned scenarios=0,assertions=0;
#define CHECK(x) do{++assertions;if(!(x)){std::fprintf(stderr,"FAIL %d: %s scenario %u\n",__LINE__,#x,scenarios);std::exit(1);}}while(false)
struct Fake:CanPort {
 mutable Time now{0};mutable unsigned clock_reads{0};unsigned jump_at{0};Time jump_by{0};PortStatus ps{};std::uint32_t alerts{0};unsigned resets{0},closes{0},submits{0},moves{0},violations{0};
 bool auto_tx{true},auto_reply{true},fd_start{true},fd_complete{true},change_position{true},bad_delta{false};
 bool slow_stop{false};Time ack_at{0};std::uint16_t ack_axis{0};std::int64_t movement_delta{3200};std::array<std::int64_t,2> speed{0,0};
 bool reset_ok{true},close_healthy{true},close_quiet{true},submit_ok{true};
 Time api_delay{0},reset_delay{0},close_delay{0},done_at{0},fd2_at{0},last_f7{0};
 bool scheduled{false};WireFrame wire{};std::array<RxFrame,128> queue{};unsigned head{0},size{0};
 std::array<std::int64_t,2> position{0,0};
 struct Sent{WireFrame frame{};Time at{0};};std::array<Sent,4096> sent{};unsigned sent_count{0};
 Time now_ms()const noexcept override{++clock_reads;if(clock_reads==jump_at)now+=jump_by;return now;}
 void push(WireFrame frame,Time at){CHECK(size<queue.size());queue[(head+size)%queue.size()]={frame,at};++size;ps.rx_pending=size;}
 WireFrame reply(std::uint16_t axis,std::uint8_t code,std::int64_t v){WireFrame r;r.id=axis;r.data[0]=code;r.dlc=(code==0x31?8:code==0x32?4:3);const unsigned bytes=r.dlc-2;auto raw=static_cast<std::uint64_t>(v);for(unsigned i=0;i<bytes;++i){r.data[bytes-i]=static_cast<std::uint8_t>(raw&255);raw>>=8;}unsigned sum=axis;for(unsigned i=0;i<r.dlc-1;++i)sum+=r.data[i];r.data[r.dlc-1]=static_cast<std::uint8_t>(sum);return r;}
 bool reset_and_start()noexcept override{++resets;now+=reset_delay;scheduled=false;size=head=0;alerts=0;fd2_at=0;ps={};ps.state=BusState::Running;return reset_ok;}
 CloseResult close()noexcept override{++closes;now+=close_delay;scheduled=false;ps.state=BusState::Stopped;ps.tx_pending=0;return{close_quiet,close_healthy};}
 void pump(){
  if(scheduled && auto_tx && now>=done_at){scheduled=false;ps.tx_pending=0;alerts|=TxSuccess;
   if(auto_reply){const auto code=wire.data[0];const auto axis=static_cast<std::uint16_t>(wire.id);
    if(code==0xFD){if(fd_start)push(reply(axis,code,1),now);if(fd_complete)fd2_at=now+5;}
    else if(code==0xF7){if(slow_stop){ack_at=now+199;ack_axis=axis;}else push(reply(axis,code,1),now);}
    else push(reply(axis,code,code==0x31?position[axis-1]:code==0x32?speed[axis-1]:1),now);
   }
  }
  if(ack_at!=0 && now>=ack_at){ack_at=0;push(reply(ack_axis,0xF7,1),now);}
  if(fd2_at!=0 && now>=fd2_at){fd2_at=0;if(change_position)position[wire.id==2?1:0]+=bad_delta?1:movement_delta;push(reply(static_cast<std::uint16_t>(wire.id),0xFD,2),now);}
 }
 bool read_alerts(std::uint32_t& a)noexcept override{pump();a=alerts;alerts=0;now+=api_delay;return true;}
 bool status(PortStatus& s)noexcept override{ps.rx_pending=size;s=ps;return true;}
 ReceiveResult receive(RxFrame& r)noexcept override{if(!size)return ReceiveResult::Empty;r=queue[head];head=(head+1)%queue.size();--size;ps.rx_pending=size;return ReceiveResult::Data;}
 bool submit(const WireFrame& f,Time deadline)noexcept override{
  ++submits;if(resets>=2 && f.data[0]!=0xF7 && now<last_f7+1300)++violations;
  if(!submit_ok||ps.tx_pending!=0||now>=deadline)return false;
  if(sent_count<sent.size())sent[sent_count++]={f,now};
  if(f.data[0]==0xFD)++moves;if(f.data[0]==0xF7)last_f7=now;
  wire=f;scheduled=true;done_at=now+(slow_stop && f.data[0]==0xF7?49:1);ps.tx_pending=1;return true;
 }
};
Profile approved(unsigned count=2){Profile p;p.gate={11,22,{1,2},static_cast<std::uint8_t>(count)};p.stop.axis_count=static_cast<std::uint8_t>(count);p.stop.heartbeat_1000_readback_confirmed=p.stop.response_bounds_approved=p.stop.position_tolerance_approved=true;p.stop.tolerance_counts=2;p.normal_approved=p.post_maintenance_enable_seed_approved=true;p.counts_per_100pulse=3200;p.dir0_sign=1;return p;}
struct Fixture {
 Fake p;Profile profile;BenchRun run;Time session{0},lease{0},ticket{0},seq{0},last_renew{0};std::uint8_t direction{0};
 static Profile fixture_profile(unsigned count,Time tolerance,int sign){auto value=approved(count);value.stop.tolerance_counts=tolerance;value.dir0_sign=static_cast<std::int8_t>(sign);return value;}
 explicit Fixture(unsigned count=2,Time tolerance=2,int sign=1):profile(fixture_profile(count,tolerance,sign)),run(p,profile){++scenarios;run.begin();}
 void step(){++p.now;run.poll();if(lease!=0 && p.now-last_renew>=200 && run.status().state!=State::Stopping && run.status().state!=State::Fault && run.status().state!=State::StoppedRecheck){last_renew=p.now;auto r=request(Op::Renew);CHECK(r.error==robot_gate::Error::None);}}
 void until(State state,Time limit=2500){for(Time i=0;i<limit && run.status().state!=state && run.status().state!=State::Fault;++i)step();CHECK(run.status().state==state);}
 robot_gate::Result request(Op op){++seq;robot_gate::Request r{11,session,seq,seq,lease,ticket,op,1,direction};return run.request(r);}
 void ready(){until(State::Ready);CHECK(run.snapshot().ready);}
 void own(){ready();session=run.open_session();CHECK(session!=0);auto r=request(Op::Acquire);CHECK(r.error==robot_gate::Error::None);lease=r.lease;last_renew=p.now;}
 void arm(){own();for(unsigned i=0;i<200;++i){auto r=request(Op::Arm);if(r.error==robot_gate::Error::None)return;CHECK(r.error==robot_gate::Error::Busy);step();}CHECK(false);}
 void move(){arm();auto t=request(Op::Ticket);CHECK(t.error==robot_gate::Error::None);ticket=t.ticket;CHECK(request(Op::Move).error==robot_gate::Error::None);step();CHECK(p.moves==1);}
 void stop(){CHECK(request(Op::Stop).error==robot_gate::Error::None);}
};
int main(){
 {++scenarios;Fake p;Profile profile;BenchRun r(p,profile);r.begin();CHECK(r.status().state==State::Fault);CHECK(p.resets==0 && p.submits==0);}
 {Fixture f;f.p.auto_tx=false;f.step();for(unsigned i=0;i<10;++i)f.step();CHECK(f.run.status().state==State::Checking);CHECK(f.p.submits==1);for(unsigned i=0;i<60 && f.run.status().state!=State::Stopping;++i)f.step();CHECK(f.run.status().fault==Fault::Tx);}
 {Fixture f(1);f.ready();CHECK(f.p.resets==1);}
 {Fixture f;f.ready();CHECK(f.run.snapshot().count==2);}

 {Fixture f;f.move();const auto* frame=&f.p.sent[f.p.sent_count-1].frame;auto expected=robot_core::mks::build_move100(1,false);CHECK(frame->data==expected.frame.data);for(unsigned i=0;i<800 && f.run.gate_status().reserved && f.run.status().state!=State::Fault;++i)f.step();CHECK(f.run.status().state==State::Ready);CHECK(!f.run.gate_status().reserved);CHECK(f.run.gate_status().armed_axis==0);CHECK(f.p.moves==1);}
 {Fixture f;f.move();f.p.change_position=false;for(unsigned i=0;i<2100 && f.run.status().state!=State::Stopping && f.run.status().state!=State::Fault;++i)f.step();CHECK(f.run.status().fault==Fault::Deadline);CHECK(f.run.status().state!=State::Ready);}
 {Fixture f;f.move();f.p.fd_start=false;for(unsigned i=0;i<20 && f.run.status().state!=State::Stopping;++i)f.step();CHECK(f.run.status().fault==Fault::Command);}
 {Fixture f;f.move();f.p.fd_complete=false;for(unsigned i=0;i<2100 && f.run.status().state!=State::Stopping && f.run.status().state!=State::Fault;++i)f.step();CHECK(f.run.status().fault==Fault::Deadline);}
 {Fixture f;f.arm();const auto age_start=f.p.now;while(f.p.now-age_start<400 && f.run.status().state!=State::Stopping)f.step();CHECK(f.run.status().fault==Fault::Observation);CHECK(f.p.moves==0);}
 {Fixture f;f.own();f.stop();const auto at=f.run.status().stop_at;f.until(State::StoppedRecheck,3600);CHECK(f.run.status().stop_verified);CHECK(f.run.status().stop_at==at);CHECK(f.p.resets==2);CHECK(f.p.violations==0);CHECK(f.run.status().closed.healthy && f.run.status().closed.quiesced);CHECK(f.request(Op::Acquire).error!=robot_gate::Error::None);}
 {Fixture f;f.own();f.p.alerts=BusOff|TxSuccess;f.step();CHECK(f.run.status().fault==Fault::Bus);const auto at=f.run.status().fault_at;for(unsigned i=0;i<3600 && f.run.status().state==State::Stopping;++i)f.step();CHECK(f.run.status().state==State::Fault);CHECK(f.run.status().stop_verified);CHECK(f.run.status().fault==Fault::Bus && f.run.status().fault_at==at);}
 {Fixture f;f.own();f.p.close_healthy=false;f.stop();for(unsigned i=0;i<3600 && f.run.status().state==State::Stopping;++i)f.step();CHECK(f.run.status().state==State::Fault);CHECK(!f.run.status().stop_verified);}
 {Fixture f;f.own();f.p.api_delay=10;f.step();CHECK(f.run.status().fault==Fault::Service);}
 {Fixture f;f.own();f.p.now+=10;f.run.poll();CHECK(f.run.status().fault==Fault::Service);}
 {Fixture f;f.own();--f.p.now;f.run.poll();CHECK(f.run.status().state==State::Stopping || f.run.status().state==State::Fault);}
 {Fixture f;f.ready();f.p.auto_reply=false;for(unsigned i=0;i<150 && f.run.status().state!=State::Stopping;++i)f.step();CHECK(f.run.status().fault==Fault::Deadline);}
 {Fixture f;f.own();f.p.reset_delay=100;f.stop();CHECK(f.run.status().state==State::Fault);CHECK(!f.run.status().stop_verified);}
 {Fixture f;f.ready();auto old=f.p.reply(1,0x31,123);old.id=0x10001;f.p.push(old,f.p.now);f.step();CHECK(f.run.status().state==State::Ready);CHECK(f.run.raw_count()>0);}
 {Fixture f;f.p.auto_tx=false;f.step();const auto at=f.p.now;for(unsigned i=0;i<49;++i){f.step();CHECK(f.run.status().state==State::Checking);}f.step();CHECK(f.run.status().fault==Fault::Tx);CHECK(f.run.status().fault_at==at+50);}
 {Fixture f;f.p.auto_reply=false;f.step();f.step();const auto tx=f.p.now;for(unsigned i=0;i<99;++i){f.step();CHECK(f.run.status().state==State::Checking);}f.step();CHECK(f.run.status().fault==Fault::Deadline);CHECK(f.run.status().fault_at==tx+100);}
 {Fixture f;f.move();f.p.fd_start=f.p.fd_complete=false;f.step();const auto tx=f.p.now;for(unsigned i=0;i<199;++i){f.step();CHECK(f.run.status().state==State::AwaitStart);}f.step();CHECK(f.run.status().fault==Fault::Deadline);CHECK(f.run.status().fault_at==tx+200);}
 {Fixture f;f.move();f.p.fd_complete=false;f.step();const auto tx=f.p.now;while(f.p.now<tx+1999)f.step();CHECK(f.run.status().state==State::Moving);f.step();CHECK(f.run.status().fault==Fault::Deadline);CHECK(f.run.status().fault_at==tx+2000);}
 {Fixture f;f.own();const auto acquired=f.p.now;f.lease=0;while(f.p.now<acquired+799)f.step();CHECK(f.run.status().state==State::Ready);f.step();CHECK(f.run.status().state==State::Stopping);CHECK(f.run.status().stop_at==acquired+800);CHECK(f.run.status().fault==Fault::None);f.until(State::StoppedRecheck,3600);CHECK(f.run.status().stop_verified);}
 {Fixture f;f.arm();std::array<std::array<Time,4>,2> latest{};for(unsigned i=0;i<f.p.sent_count;++i){const auto& t=f.p.sent[i];int ci=-1;for(unsigned c=0;c<4;++c)if(t.frame.data[0]==std::array<unsigned,4>{0xF1,0x31,0x32,0x3A}[c])ci=static_cast<int>(c);if(ci>=0)latest[t.frame.id-1][static_cast<unsigned>(ci)]=t.at+1;}Time oldest=std::numeric_limits<Time>::max();for(const auto& a:latest)for(auto time:a)if(time<oldest)oldest=time;while(f.p.now<oldest+399)f.step();CHECK(f.run.status().state==State::Ready);f.step();CHECK(f.run.status().fault==Fault::Observation);CHECK(f.run.status().fault_at==oldest+400);}
 {Fixture f;f.move();f.p.bad_delta=true;for(unsigned i=0;i<2100 && f.run.status().state!=State::Stopping && f.run.status().state!=State::Fault;++i)f.step();CHECK(f.run.status().fault==Fault::Deadline);}
 {Fixture f;f.own();auto old=f.seq;CHECK(f.request(Op::Renew).error==robot_gate::Error::None);robot_gate::Request replay{11,f.session,old,old,f.lease,0,Op::Move,1,0};CHECK(f.run.request(replay).error==robot_gate::Error::Replay);CHECK(f.p.moves==0);}
 {Fixture f;f.own();f.stop();const auto stamp=f.run.status().stop_at;f.p.now=stamp+600;f.run.poll();CHECK(f.run.status().state==State::Fault);CHECK(f.run.status().stop_at==stamp);CHECK(f.run.status().fault==Fault::StopTiming);}
 {Fixture f;f.own();f.stop();const auto stamp=f.run.status().stop_at;f.p.now=stamp+3600;f.run.poll();CHECK(f.run.status().state==State::Fault);CHECK(!f.run.status().stop_verified);}
 {Fixture f;f.own();f.p.close_delay=10;f.stop();for(unsigned i=0;i<3600 && f.run.status().state==State::Stopping;++i)f.step();CHECK(f.run.status().state==State::Fault);CHECK(!f.run.status().stop_verified);}
 {Fixture f;f.move();f.stop();CHECK(f.p.moves==1);f.until(State::StoppedRecheck,3600);CHECK(f.p.moves==1 && f.p.violations==0);}
 {Fixture f;f.arm();auto t=f.request(Op::Ticket);f.ticket=t.ticket;CHECK(f.request(Op::Move).error==robot_gate::Error::None);f.stop();CHECK(f.p.moves==0);f.until(State::StoppedRecheck,3600);CHECK(f.p.moves==0);}
 {Fixture f;f.own();f.p.alerts=TxFailed|TxSuccess;f.step();CHECK(f.run.status().fault==Fault::Tx);}
 {Fixture f;f.own();for(unsigned i=0;i<17;++i)f.p.push(f.p.reply(1,0x31,0),f.p.now);f.step();CHECK(f.run.status().fault==Fault::Rx);}
 {Fixture f;f.own();const auto resets=f.p.resets;f.run.begin();CHECK(f.p.resets==resets);f.stop();f.run.begin();CHECK(f.p.resets==resets+1);}
 // R1 directional counterexamples: large tolerance must not hide zero or reversed motion.
 for(int sign:{1,-1})for(unsigned dir:{0u,1u})for(int mode:{0,1}){
  Fixture f(2,6400,sign);f.direction=static_cast<std::uint8_t>(dir);f.p.movement_delta=mode==0?0:-(dir==0?sign:-sign);f.move();
  for(unsigned i=0;i<2100 && f.run.status().state!=State::Stopping && f.run.status().state!=State::Fault;++i)f.step();
  CHECK(f.run.status().fault==Fault::Deadline);CHECK(f.run.status().state!=State::Ready);
 }
 for(int sign:{1,-1})for(unsigned dir:{0u,1u}){
  Fixture f(2,2,sign);f.direction=static_cast<std::uint8_t>(dir);f.p.movement_delta=3200*(dir==0?sign:-sign);f.move();
  for(unsigned i=0;i<800 && f.run.gate_status().reserved && f.run.status().state!=State::Fault;++i)f.step();CHECK(f.run.status().state==State::Ready);CHECK(!f.run.gate_status().reserved);
 }
 {++scenarios;Fake p;auto profile=approved();profile.counts_per_100pulse=0;BenchRun run(p,profile);run.begin();CHECK(run.status().fault==Fault::Profile);CHECK(p.resets==0 && p.submits==0);}
 // Genuine correlated nonselected speed evidence while F1 remains stopped.
 {Fixture f;f.move();f.p.fd_complete=false;f.p.speed[1]=1;for(unsigned i=0;i<200 && f.run.status().state!=State::Stopping;++i)f.step();CHECK(f.run.status().fault==Fault::Observation);CHECK(f.run.status().state==State::Stopping);}
 // Valid correlated positions already reached expected delta before FD2.
 {Fixture f;f.move();f.p.fd_complete=false;f.p.position[0]=3200;for(unsigned i=0;i<400;++i)f.step();CHECK(f.run.status().state==State::Moving);CHECK(f.run.gate_status().reserved);
  f.p.auto_reply=false;for(unsigned i=0;i<25 && !f.p.scheduled;++i)f.step();CHECK(f.p.scheduled);const auto pending=f.p.wire;f.step();
  f.p.push(f.p.reply(1,0xFD,2),f.p.now+1);const auto code=pending.data[0];f.p.push(f.p.reply(static_cast<std::uint16_t>(pending.id),code,code==0x31?f.p.position[pending.id-1]:code==0x32?0:1),f.p.now+1);f.step();
  CHECK(f.run.status().state==State::Completing);CHECK(f.run.gate_status().reserved);
  for(unsigned i=0;i<3;++i)f.p.push(f.p.reply(1,0x31,3200),f.p.now+1);f.step();CHECK(f.run.gate_status().reserved);CHECK(f.run.status().state!=State::Ready);
  for(unsigned i=0;i<150 && f.run.status().state!=State::Stopping;++i)f.step();CHECK(f.run.status().fault==Fault::Deadline);
 }
 {Fixture f;f.own();const auto original=f.p.now;f.p.slow_stop=true;f.p.jump_at=f.p.clock_reads+14;f.p.jump_by=9;f.stop();CHECK(f.run.status().stop_at==original);CHECK(f.p.sent[f.p.sent_count-1].at==original+9);
  for(unsigned i=0;i<600 && f.run.status().preparation_at==0 && f.run.status().state==State::Stopping;++i)f.step();
  CHECK(f.run.status().preparation_at!=0);CHECK(f.run.status().preparation_at-original<519);
  std::printf("PHASE nearworst t0=%llu inner_begin=%llu prep=%llu elapsed=%llu state=%u\n",static_cast<unsigned long long>(original),static_cast<unsigned long long>(original+9),static_cast<unsigned long long>(f.run.status().preparation_at),static_cast<unsigned long long>(f.run.status().preparation_at-original),static_cast<unsigned>(f.run.stop_link().core().state()));
  f.until(State::StoppedRecheck,3600);CHECK(f.run.status().stop_verified);
 }
 {Fixture f;f.own();const auto original=f.p.now;f.p.reset_delay=90;f.stop();CHECK(f.run.status().state==State::Fault);CHECK(f.run.status().fault==Fault::StopTiming);CHECK(!f.run.status().stop_verified);
  std::printf("PHASE crossing t0=%llu now=%llu rejected_duration=%llu inner_phase=%u outer_fault=%u\n",static_cast<unsigned long long>(original),static_cast<unsigned long long>(f.p.now),static_cast<unsigned long long>(f.p.now-original),static_cast<unsigned>(f.run.stop_link().core().state()),static_cast<unsigned>(f.run.status().fault));
 }
 std::printf("PASS scenarios=%u assertions=%u\n",scenarios,assertions);return 0;
}
