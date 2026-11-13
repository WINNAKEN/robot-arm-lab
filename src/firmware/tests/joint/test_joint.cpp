#define main original_run_tests
#include "../run/test_run.cpp"
#undef main
#include "oracle.hpp"
#include <cmath>
namespace joint=robot_joint;

struct JointFixture {
    Fake p; Profile profile; std::array<joint::Calibration,2> input;
    BenchRun run; Time session{0},lease{0},ticket{0},seq{0},renewed{0};unsigned axis{1};
    static Profile config(Time boot){auto p=approved();p.gate.boot=boot;return p;}
    static std::array<joint::Calibration,2> calibrations(Time boot){
        return {{{true,joint::Layout::FixedV2_025,boot,22,1,1,200,16,27.,1},
                 {true,joint::Layout::FixedV2_025,boot,22,2,2,200,16,9.,-1}}};
    }
    explicit JointFixture(unsigned selected=1,Time boot=11,bool begin=true)
        : profile(config(boot)),input(calibrations(boot)),run(p,profile,input),axis(selected){++scenarios;if(begin)run.begin();}
    robot_gate::Request message(Op op){++seq;return {profile.gate.boot,session,seq,seq,lease,ticket,op,static_cast<std::uint16_t>(axis),0};}
    robot_gate::Result raw(Op op){return run.request(message(op));}
    void step(){++p.now;run.poll();if(lease && p.now-renewed>=200 && run.status().state!=State::Stopping && run.status().state!=State::Fault && run.status().state!=State::StoppedRecheck){renewed=p.now;CHECK(raw(Op::Renew).error==robot_gate::Error::None);}}
    void until(State state,Time limit=2500){for(Time n=0;n<limit && run.status().state!=state && run.status().state!=State::Fault;++n)step();CHECK(run.status().state==state);}
    void permit(){until(State::Ready);session=run.open_session();CHECK(session!=0);const auto own=raw(Op::Acquire);CHECK(own.error==robot_gate::Error::None);lease=own.lease;renewed=p.now;
        bool armed=false;for(unsigned n=0;n<200;++n){const auto a=raw(Op::Arm);if(a.error==robot_gate::Error::None){armed=true;break;}CHECK(a.error==robot_gate::Error::Busy);step();}CHECK(armed);
        const auto t=raw(Op::Ticket);CHECK(t.error==robot_gate::Error::None);ticket=t.ticket;}
    joint::Step amount(bool positive=true,joint::StepUnit unit=joint::StepUnit::CadDegrees)const {
        const double deg=360.*100./(200.*16.*input[axis-1].reduction)*(positive?1.:-1.);
        return {unit,unit==joint::StepUnit::CadDegrees?deg:deg*joint::pi/180.};
    }
    robot_gate::Result move(joint::Step step){return run.request_joint_step(message(Op::Move),axis,step);}
};

static void coordinates(){
    for(const auto& row:oracle){
        const auto got=joint::convert(row.joint,{static_cast<joint::Space>(row.space),row.input});
        CHECK(got.ok);CHECK(std::fabs(got.cad_deg-row.cad)<1e-10);
        CHECK(std::fabs(got.delta_rad-row.delta)<1e-12);CHECK(std::fabs(got.geometric_rad-row.geometric)<1e-12);
        const auto back=joint::convert(row.joint,{joint::Space::CoreGeometricRadians,got.geometric_rad});
        CHECK(back.ok);CHECK(std::fabs(back.cad_deg-got.cad_deg)<1e-10);
    }
    for(unsigned j: {0u,7u,65535u})CHECK(!joint::convert(j,{}).ok);
    for(double x:{std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN()})CHECK(!joint::convert(1,{joint::Space::CadDegrees,x}).ok);
    CHECK(!joint::convert(1,{static_cast<joint::Space>(255),1.}).ok);
    CHECK(!joint::convert(1,{joint::Space::CoreDeltaRadians,std::numeric_limits<double>::max()}).ok);
    for(unsigned j=1;j<=6;++j){auto c=JointFixture::calibrations(11)[0];c.joint=static_cast<std::uint16_t>(j);c.fullsteps=400;
        const auto prepared=joint::prepare(c,j,{joint::StepUnit::CadDegrees,360.*100./(400.*16.*27.)});CHECK(prepared.ok&&prepared.direction==0);}
}

static void accepted_paths(){
    for(unsigned axis:{1u,2u})for(bool positive:{false,true})for(auto unit:{joint::StepUnit::CadDegrees,joint::StepUnit::CoreRadians}){
        JointFixture f(axis);f.permit();const auto amount=f.amount(positive,unit);
        const bool dir1=positive!=(axis==1);f.p.movement_delta=dir1?-3200:3200;
        CHECK(f.move(amount).error==robot_gate::Error::None);CHECK(f.p.moves==0);f.step();CHECK(f.p.moves==1);
        const auto expected=robot_core::mks::build_move100(static_cast<std::uint16_t>(axis),dir1);
        unsigned found=0;for(unsigned i=0;i<f.p.sent_count;++i)if(f.p.sent[i].frame.data[0]==0xFD){++found;CHECK(f.p.sent[i].frame.id==axis);CHECK(f.p.sent[i].frame.dlc==8);CHECK(f.p.sent[i].frame.data==expected.frame.data);}
        CHECK(found==1);f.until(State::Ready);CHECK(f.p.moves==1);
        CHECK(f.run.request_joint_step(f.message(Op::Stop),999,{static_cast<joint::StepUnit>(255),std::numeric_limits<double>::quiet_NaN()}).error==robot_gate::Error::None);
        f.until(State::StoppedRecheck,3600);CHECK(f.run.status().stop_verified);
    }
}

static void invalid_cases(){
    for(unsigned variant=0;variant<20;++variant){
        auto profile=approved();Fake p;auto calibration=JointFixture::calibrations(11);
        auto step=joint::Step{joint::StepUnit::CadDegrees,360.*100./(200.*16.*27.)};
        auto joint_id=1u;auto& c=calibration[0];
        switch(variant){case 0:c.measured=false;break;case 1:c.layout=joint::Layout::Unknown;break;
        case 2:c.boot=12;break;case 3:c.profile=23;break;case 4:c.axis=2;break;case 5:c.joint=2;break;
        case 6:c.fullsteps=0;break;case 7:c.microsteps=32;break;case 8:c.reduction=0;break;
        case 9:c.reduction=std::numeric_limits<double>::infinity();break;case 10:c.dir0_joint_sign=0;break;
        case 11:step.value=0;break;case 12:step.value*=2;break;case 13:step.value=std::numeric_limits<double>::quiet_NaN();break;
        case 14:step.value=std::numeric_limits<double>::infinity();break;case 15:step.unit=static_cast<joint::StepUnit>(255);break;
        case 16:joint_id=0;break;case 17:joint_id=7;break;case 18:step.value=std::numeric_limits<double>::max();break;
        default:c.reduction=std::numeric_limits<double>::quiet_NaN();break;}
        BenchRun run(p,profile,calibration);run.begin();
        // Invalid conversion must not reserve an intent even with an issued permit.
        Time session=0,lease=0,ticket=0,seq=0;
        auto request=[&](Op op){++seq;return robot_gate::Request{11,session,seq,seq,lease,ticket,op,1,0};};
        for(unsigned i=0;i<2000 && run.status().state!=State::Ready;++i){++p.now;run.poll();}
        CHECK(run.status().state==State::Ready);session=run.open_session();const auto own=run.request(request(Op::Acquire));CHECK(own.error==robot_gate::Error::None);lease=own.lease;
        for(unsigned i=0;i<200;++i){const auto a=run.request(request(Op::Arm));if(a.error==robot_gate::Error::None)break;CHECK(a.error==robot_gate::Error::Busy);++p.now;run.poll();}
        const auto t=run.request(request(Op::Ticket));CHECK(t.error==robot_gate::Error::None);ticket=t.ticket;
        CHECK(run.request_joint_step(request(Op::Move),joint_id,step).error!=robot_gate::Error::None);
        CHECK(!run.gate_status().reserved);++p.now;run.poll();CHECK(p.moves==0);
    }
    {Fixture old;old.arm();auto t=old.request(Op::Ticket);old.ticket=t.ticket;
     auto r=robot_gate::Request{11,old.session,++old.seq,old.seq,old.lease,old.ticket,Op::Move,1,0};
     CHECK(old.run.request_joint_step(r,1,{joint::StepUnit::CadDegrees,1.}).error!=robot_gate::Error::None);CHECK(old.p.moves==0);}
    {Fixture f;f.arm();auto r=robot_gate::Request{11,f.session,++f.seq,f.seq,f.lease,0,Op::Stop,1,0};
     CHECK(f.run.request_joint_step(r,0,{static_cast<joint::StepUnit>(255),std::numeric_limits<double>::quiet_NaN()}).error==robot_gate::Error::None);
     f.until(State::StoppedRecheck,3600);CHECK(f.run.status().stop_verified&&f.p.moves==0);}
    for(unsigned variant=0;variant<5;++variant){JointFixture f;f.permit();auto r=f.message(Op::Move);
        switch(variant){case 0:++r.boot;break;case 1:++r.session;break;case 2:++r.lease;break;case 3:++r.ticket;break;default:r.axis=2;break;}
        CHECK(f.run.request_joint_step(r,1,f.amount()).error!=robot_gate::Error::None);f.step();CHECK(f.p.moves==0);}
}

static void lifetime(){
    {JointFixture f;f.permit();const auto amount=f.amount();f.input[0].measured=false;f.input[0].dir0_joint_sign=-1;f.input[0].reduction=9.;
     CHECK(f.move(amount).error==robot_gate::Error::None);f.step();CHECK(f.p.moves==1);CHECK((f.p.wire.data[1]&0x80)==0);}
    {JointFixture f;f.permit();CHECK(f.move(f.amount()).error==robot_gate::Error::None);CHECK(f.run.gate_status().reserved);CHECK(f.p.moves==0);
     f.run.revoke_joint_mapping();CHECK(!f.run.gate_status().reserved);CHECK(f.run.status().state==State::Stopping);CHECK(f.run.status().fault==Fault::Profile);
     const auto first=f.run.status();CHECK(f.move(f.amount()).error!=robot_gate::Error::None);f.run.revoke_joint_mapping();CHECK(f.run.status().fault_at==first.fault_at);CHECK(f.run.status().stop_at==first.stop_at);
     f.until(State::Fault,3600);CHECK(f.run.status().stop_verified);CHECK(f.p.moves==0);bool f7=false;for(unsigned i=0;i<f.p.sent_count;++i)f7=f7||f.p.sent[i].frame.data[0]==0xF7;CHECK(f7);f.run.begin();CHECK(f.move(f.amount()).error!=robot_gate::Error::None);CHECK(f.p.moves==0);}
    {JointFixture f(1,11,false);f.run.revoke_joint_mapping();CHECK(f.p.submits==0&&f.p.resets==0);f.run.begin();f.permit();CHECK(f.move(f.amount()).error!=robot_gate::Error::None);f.step();CHECK(f.p.moves==0);}
    {JointFixture f;f.permit();f.p.now+=10;f.run.poll();
     const auto first=f.run.status();CHECK(first.fault!=Fault::None);f.run.revoke_joint_mapping();CHECK(f.run.status().fault==first.fault);CHECK(f.run.status().fault_at==first.fault_at);}
    {JointFixture old;old.permit();const auto request=old.message(Op::Move);old.run.revoke_joint_mapping();old.until(State::Fault,3600);CHECK(old.run.status().stop_verified);
     JointFixture fresh(1,77);fresh.permit();CHECK(fresh.run.request_joint_step(request,1,fresh.amount()).error!=robot_gate::Error::None);fresh.step();CHECK(fresh.p.moves==0);}
}

int main(){CHECK(original_run_tests()==0);coordinates();accepted_paths();invalid_cases();lifetime();
    std::printf("JOINT PASS oracle=%zu scenarios=%u assertions=%u hardware=NOT_RUN\n",oracle.size(),scenarios,assertions);return 0;}
