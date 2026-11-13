#include "robot_gate/control_gate.hpp"
#include <cstdio>
#include <cstdlib>
#include <limits>
using namespace robot_gate;
static unsigned checks=0, scenarios=0;
#define CHECK(x) do { ++checks; if (!(x)) { std::fprintf(stderr,"FAIL line %d: %s\n",__LINE__,#x); std::exit(1); } } while(false)
struct Fixture {
    Config c{11,22,{1,2},2}; ControlGate gate{c}; Snapshot s{}; Id now{10}, session{0}, other{0}, lease{0}, ticket{0}, sequence{0};
    Fixture() { ++scenarios; s.revision=1;s.profile=22;s.approved=s.ready=s.stopped=true; for(auto& a:s.axes) a.valid=a.enabled=true;
        session=gate.open_session(now,s); CHECK(session!=0); }
    Request request(Op op,std::uint16_t axis=1) { ++sequence; return {11,session,sequence,sequence,lease,ticket,op,axis,0}; }
    Result send(Op op,std::uint16_t axis=1) {return gate.handle(now,s,request(op,axis));}
    void own() { auto r=send(Op::Acquire);CHECK(r.error==Error::None);lease=r.lease;CHECK(lease!=0); }
    void permit() {own();CHECK(send(Op::Arm).error==Error::None);}
    void issue() {permit(); auto r=send(Op::Ticket);CHECK(r.error==Error::None);ticket=r.ticket;CHECK(ticket!=0);}
    void move() {issue();CHECK(send(Op::Move).error==Error::None);CHECK(gate.status().reserved);}
};
int main() {
    { Fixture f; f.s.approved=false; ++f.s.revision; CHECK(f.send(Op::Acquire).error==Error::Denied); CHECK(!f.gate.status().fault); }
    { Fixture f; f.s.axes[1].valid=false;++f.s.revision; CHECK(f.send(Op::Acquire).error==Error::Denied); }
    { Fixture f; f.own(); f.other=f.gate.open_session(f.now,f.s);CHECK(f.other!=0);CHECK(f.gate.open_session(f.now,f.s)==0);
      auto r=f.request(Op::Acquire);r.session=f.other;CHECK(f.gate.handle(f.now,f.s,r).error==Error::Busy);
      r.op=Op::Stop;r.seq=0;r.request=0;CHECK(f.gate.handle(f.now,f.s,r).error==Error::None);CHECK(f.gate.status().stopped_latched); }
    { Fixture f; auto r=f.request(Op::Stop);r.boot=10;CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadBoot);r.boot=11;r.session=999;CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadSession);CHECK(!f.gate.status().stopped_latched); }
    for (Id offset : {Id{799},Id{800},Id{801}}) {Fixture f;f.own();f.now+=offset;auto r=f.send(Op::Renew);CHECK((r.error==Error::None)==(offset<800));CHECK(f.gate.status().stopped_latched==(offset>=800));}
    {Fixture f;f.own();auto r=f.request(Op::Renew);f.now=700;CHECK(f.gate.handle(f.now,f.s,r).error==Error::None);const auto deadline=f.gate.status().lease_until;f.now=701;CHECK(f.gate.handle(f.now,f.s,r).error==Error::Replay);CHECK(f.gate.status().lease_until==deadline);}
    {Fixture f;f.permit();CHECK(f.send(Op::Arm,2).error==Error::AxisDenied);CHECK(f.send(Op::Ticket,2).error==Error::AxisDenied);}
    for (Id offset : {Id{499},Id{500},Id{501}}) {Fixture f;f.issue();f.now+=offset;CHECK((f.send(Op::Move).error==Error::None)==(offset<500));}
    {Fixture f;f.issue();auto r=f.request(Op::Move);CHECK(f.gate.handle(f.now,f.s,r).error==Error::None);CHECK(f.gate.handle(f.now,f.s,r).error==Error::Replay);Intent i;CHECK(f.gate.take_intent(f.now,f.s,i));CHECK(i.pulses==100 && i.speed==5 && i.acceleration==2 && i.direction==0);CHECK(!f.gate.take_intent(f.now,f.s,i));CHECK(f.send(Op::Move).error==Error::Busy);}
    {Fixture f;f.issue();auto r=f.request(Op::Move);r.lease++;CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadLease);r=f.request(Op::Move);r.ticket++;CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadTicket);}
    {Fixture f;f.issue();auto r=f.request(Op::Move);r.direction=2;CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadRequest);r=f.request(Op::Move);r.direction=1;CHECK(f.gate.handle(f.now,f.s,r).error==Error::None);Intent i;CHECK(f.gate.take_intent(f.now,f.s,i));CHECK(i.direction==1);}
    for (int reason=0;reason<5;++reason) {Fixture f;f.move();if(reason==0)CHECK(f.send(Op::Stop).error==Error::None);if(reason==1){++f.s.revision;f.s.fault=true;}if(reason==2) f.now+=800;if(reason==3)++f.s.revision;if(reason==4)f.now+=500;Intent i;CHECK(!f.gate.take_intent(f.now,f.s,i));CHECK(f.gate.status().stopped_latched);}
    {Fixture f;f.move();Intent i;CHECK(f.gate.take_intent(f.now,f.s,i));++f.s.revision;f.s.moving=f.s.axes[0].moving=true;f.s.stopped=f.s.ready=false;f.gate.tick(++f.now,f.s);CHECK(!f.gate.status().stopped_latched);CHECK(f.gate.status().reserved);++f.s.revision;f.s.moving=f.s.axes[0].moving=false;f.s.stopped=f.s.ready=true;CHECK(f.gate.complete(++f.now,f.s,i.id));CHECK(!f.gate.status().reserved && f.gate.status().armed_axis==0);}
    {Fixture f;f.move();Intent i;CHECK(f.gate.take_intent(f.now,f.s,i));++f.s.revision;f.s.moving=f.s.axes[1].moving=true;f.s.stopped=f.s.ready=false;f.gate.tick(++f.now,f.s);CHECK(f.gate.status().stopped_latched);}
    for(int bad=0;bad<4;++bad){Fixture f;f.move();Intent i;if(bad!=0)CHECK(f.gate.take_intent(f.now,f.s,i));if(bad!=2)++f.s.revision;if(bad==3)f.s.axes[0].enabled=false;CHECK(!f.gate.complete(f.now,f.s,bad==1?i.id+1:i.id));CHECK(f.gate.status().stopped_latched);}
    {Fixture f;Id old=f.session;f.gate.close_session(f.now,f.s,old);Id fresh=f.gate.open_session(f.now,f.s);CHECK(fresh!=old && fresh!=0);auto r=f.request(Op::Acquire);CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadSession);}
    {Fixture f;f.own();f.gate.close_session(f.now,f.s,f.session);CHECK(f.gate.status().stopped_latched);}
    {Fixture f;f.own();f.gate.tick(f.now-1,f.s);CHECK(f.gate.status().fault && f.gate.status().error==Error::ClockReversed);}
    {Fixture f;f.now=std::numeric_limits<Id>::max()-100;CHECK(f.send(Op::Acquire).error==Error::Overflow);CHECK(f.gate.status().fault);}
    {Fixture f;auto r=f.request(Op::Acquire);r.seq=std::numeric_limits<Id>::max();CHECK(f.gate.handle(f.now,f.s,r).error==Error::IdentityExhausted);CHECK(f.gate.status().fault);}
    {Fixture f;f.own();auto r=f.request(Op::Renew);CHECK(f.gate.handle(f.now,f.s,r).error==Error::None);auto stale=f.request(Op::Renew);stale.request=r.request;CHECK(f.gate.handle(f.now,f.s,stale).error==Error::Replay);}
    {Fixture f;f.own();CHECK(f.send(Op::Stop).error==Error::None);Id at;CHECK(f.gate.take_stop(f.now,f.s,at));CHECK(at==10);f.now=20;CHECK(f.send(Op::Stop).error==Error::None);CHECK(!f.gate.take_stop(f.now,f.s,at));CHECK(f.gate.status().stop_started_at==10);}
    for(int kind=0;kind<3;++kind){Fixture f;f.own();++f.s.revision;if(kind==0)++f.s.profile;if(kind==1)f.s.count=1;if(kind==2)f.s.axes[0].id=2;f.gate.tick(f.now,f.s);CHECK(f.gate.status().fault && f.gate.status().error==Error::ProfileChanged);}
    {Fixture f;f.s.ready=false;f.gate.tick(f.now,f.s);CHECK(f.gate.status().fault);}
    {Fixture f;f.s.revision=0;f.gate.tick(f.now,f.s);CHECK(f.gate.status().fault);}
    {Fixture f;auto r=f.request(static_cast<Op>(99));CHECK(f.gate.handle(f.now,f.s,r).error==Error::BadRequest);}
    {Fixture f;f.own();f.gate.tick(f.now-1,f.s);CHECK(f.send(Op::Stop).error==Error::None);CHECK(f.gate.status().error==Error::ClockReversed);}
    for(std::uint16_t a:{std::uint16_t{1},std::uint16_t{2}}){++scenarios;Config c{11,22,{a,0},1};ControlGate g(c);Snapshot s; s.profile=22;s.revision=1;s.count=1;s.axes[0]={a,true,true,false};s.approved=s.ready=s.stopped=true;CHECK(g.open_session(0,s)!=0);}
    {++scenarios;Config c;ControlGate g(c);CHECK(g.status().fault);}
    std::printf("PASS scenarios=%u assertions=%u\n",scenarios,checks);return 0;
}
