#include "robot_phone/owner.hpp"
#include <limits>
namespace robot_phone {
namespace {std::string_view secret(const Secret& s)noexcept{return {s.data(),32};
}
unsigned slot(Listener l)noexcept{return l==Listener::Stop?1:0;
}
}
Owner::Owner(robot_can::CanPort& p,const robot_boot::Profile& profile,const Seed& seed,const std::array<robot_joint::Calibration,2>& calibration)noexcept:port_(p),profile_(profile),seed_(seed),boot_(p,profile),run_(p,profile.run,calibration){snapshot_.boot=seed.boot;
snapshot_.selected_axis=profile.run.selected_axis;
// Unavailable topology is not a normalized/authorized profile. Core still sees
// the original immutable count and records its own Profile denial.
snapshot_.axis_count=profile.run.gate.count>=1&&profile.run.gate.count<=snapshot_.positions.size()?profile.run.gate.count:0;
}
void Owner::begin()noexcept{if(begun_)return;
begun_=true;
boot_.begin();
publish();
}
bool Owner::enqueue(const Envelope& e)noexcept{const auto i=slot(e.listener);
if(!begun_||pending_[i]||(i==0&&handoff_waiting_)||e.job==0)return false;
queue_[i]=e;
pending_[i]=true;
return true;
}
bool Owner::mint_handoff()noexcept{robot_run::BootEvidence evidence;
if(!boot_.take_evidence(evidence))return false;
run_.begin_from_boot(static_cast<robot_run::BootEvidence&&>(evidence));
run_active_=true;
phase(Phase::RunChecking);
return true;
}
bool Owner::transfer_stop(const Wire& w,unsigned user)const noexcept{
 return w.op==Op::Stop&&w.boot==seed_.boot&&user==transfer_.session&&
  w.ticket==transfer_.id&&transfer_.id!=0&&w.axis==transfer_.axis&&
  (transfer_.state==TransferState::Pending||transfer_.state==TransferState::Granted)&&
  ((snapshot_.phase==Phase::RunChecking&&snapshot_.generation==transfer_.generation+1)||
   (snapshot_.phase==Phase::Run&&snapshot_.generation==transfer_.generation+2))&&
  w.phase>=transfer_.generation&&w.phase<=transfer_.generation+2;
}
void Owner::transfer_result(Result& out)const noexcept{
 out.transfer_id=transfer_.id;out.transfer_state=transfer_.state;
 out.transfer_generation=transfer_.generation+2;out.pending_until=transfer_.until;
 out.grant_at=transfer_.grant_at;out.sequence_floor=transfer_.attempts?1:0;
 const auto g=run_.gate_status();const auto now=port_.now_ms();
 if(transfer_.state==TransferState::Granted&&snapshot_.phase==Phase::Run&&
    g.owner==sessions_[transfer_.session].run_session&&g.lease==transfer_.lease&&now<g.lease_until){
  out.lease=transfer_.lease;out.lease_until=g.lease_until;
 }else if(transfer_.state==TransferState::Granted)out.transfer_state=TransferState::Cancelled;
 if(transfer_.state==TransferState::Pending&&now>=transfer_.until)out.transfer_state=TransferState::Expired;
}
void Owner::stop_transfer()noexcept{
 auto& s=sessions_[transfer_.session];
 if(s.run_session==0)s.run_session=run_.open_session(seed_.principals[transfer_.session]);
 if(s.run_session!=0)run_.request({profile_.run.gate.boot,s.run_session,0,0,0,0,robot_gate::Op::Stop,transfer_.axis,0});
}
void Owner::advance_transfer()noexcept{
 auto& t=transfer_;
 if(t.state!=TransferState::Pending&&t.state!=TransferState::Granted)return;
 const auto now=port_.now_ms();
 if(snapshot_.phase>=Phase::Stopping){t.state=TransferState::Cancelled;t.lease=0;return;}
 if(t.state==TransferState::Granted){const auto g=run_.gate_status();
  if(g.owner!=sessions_[t.session].run_session||g.lease!=t.lease||now>=g.lease_until){t.state=TransferState::Expired;t.lease=0;}
  return;
 }
 if(now>=t.until){t.state=TransferState::Expired;stop_transfer();return;}
 if(!run_.acquisition_ready())return;
 auto& s=sessions_[t.session];++t.attempts;
 s.run_session=run_.open_session(seed_.principals[t.session]);
 const auto r=run_.request({profile_.run.gate.boot,s.run_session,1,1,0,0,robot_gate::Op::Acquire,t.axis,0});
 if(r.error!=robot_gate::Error::None){t.state=TransferState::Failed;stop_transfer();return;}
 t.state=TransferState::Granted;t.lease=r.lease;t.grant_at=port_.now_ms();
}
int Owner::authenticate(const Secret& c)const noexcept{for(unsigned i=0;i<2;++i)if(sessions_[i].paired&&equal_secret(secret(c),secret(seed_.credentials[i])))return static_cast<int>(i);
return -1;
}
bool Owner::budget(Session& s,Time now)noexcept{if(now<s.last_rate)return false;
auto delta=now-s.last_rate;
if(delta>400)delta=400;
s.credits=static_cast<unsigned>(s.credits+delta);
if(s.credits>400)s.credits=400;
s.last_rate=now;
if(s.credits<100)return false;
s.credits-=100;
return true;
}
void Owner::phase(Phase value)noexcept{if(snapshot_.phase==value)return;
snapshot_.phase=value;
if(snapshot_.generation!=std::numeric_limits<Time>::max())++snapshot_.generation;
for(auto& s:sessions_){s.seq=s.request=0;
} }
void Owner::execute(const Envelope& e,Result& out)noexcept{
 const auto now=port_.now_ms();
 out={};
 out.job=e.job;
 out.accepted_at=now;
 if(e.pairing){if(e.listener!=Listener::Normal||!equal_secret(secret(e.credential),secret(seed_.pairing))){out.error=Error::Auth;
 return;
 }
 for(unsigned i=0;i<2;++i)if(!sessions_[i].paired){sessions_[i].paired=true;
 sessions_[i].last_rate=now;
 out.paired=true;
 out.credential=seed_.credentials[i];
 return;
 }
 out.error=Error::SessionFull;
 return;
 }
 const int authenticated=authenticate(e.credential);
 if(authenticated<0){out.error=Error::Auth;
 return;
 }
 auto& s=sessions_[static_cast<unsigned>(authenticated)];
 const auto& w=e.wire;
 if((e.listener==Listener::Stop)!=(w.op==Op::Stop)){out.error=Error::Denied;
 return;
 }
 // Read-only receipt identity survives precisely the intended phase changes.
 if(w.op==Op::HandoffResult){
  if(w.boot!=seed_.boot){out.error=Error::Phase;return;}
  if(e.enqueued_at>now||now-e.enqueued_at>=50){out.error=Error::Stale;return;}
  if(snapshot_.adapter_fault!=AdapterFault::None){out.error=Error::Denied;return;}
  if(transfer_.state==TransferState::None||transfer_.session!=static_cast<unsigned>(authenticated)||
     w.ticket!=transfer_.id||w.axis!=transfer_.axis){out.error=Error::Denied;return;}
  if(!budget(s,now)){out.error=Error::Rate;return;}
  transfer_result(out);return;
 }
 if(w.boot!=seed_.boot||w.phase!=snapshot_.generation){out.error=Error::Phase;
 if(!transfer_stop(w,static_cast<unsigned>(authenticated)))return;
 out.error=Error::None;
 }
 if(e.enqueued_at>now||now-e.enqueued_at>=50){if(w.op!=Op::Stop){out.error=Error::Stale;
 return;
 }
 snapshot_.queue_stop_late=true;
 snapshot_.adapter_fault=AdapterFault::StopQueueLate;
 }
 if(w.op!=Op::Stop&&snapshot_.adapter_fault!=AdapterFault::None){out.error=Error::Denied;
 return;
 }
 if(w.op!=Op::Stop){if(w.seq==0||w.request==0||w.seq<=s.seq||w.request<=s.request||w.seq==std::numeric_limits<Time>::max()||w.request==std::numeric_limits<Time>::max()){out.error=Error::Replay;
 return;
 }
 if(!budget(s,now)){out.error=Error::Rate;
 return;
 }
 s.seq=w.seq;
 s.request=w.request;
 }
 if(transfer_.state==TransferState::Pending&&w.op!=Op::Stop){out.error=Error::Busy;return;}
 if(w.op==Op::HandoffAcquire){
  const auto b=boot_.status();
  if(run_active_||transfer_.state!=TransferState::None||b.state!=robot_boot::State::Granted||
     b.owner!=s.boot_session||w.lease==0||w.lease!=s.boot_lease||w.axis!=profile_.run.selected_axis||
     w.ticket!=0||now>=b.lease_until||now>std::numeric_limits<Time>::max()-700||
     snapshot_.generation>std::numeric_limits<Time>::max()-3){out.error=Error::Denied;return;}
  const auto generation=snapshot_.generation;
  if(!mint_handoff()){out.error=Error::Busy;return;}
  transfer_.state=TransferState::Pending;transfer_.session=static_cast<unsigned>(authenticated);
  transfer_.id=w.request;transfer_.generation=generation;transfer_.axis=w.axis;
  transfer_.until=now+700<b.lease_until?now+700:b.lease_until;
  transfer_result(out);return;
 }
 if(!run_active_){
  if(s.boot_session==0)s.boot_session=boot_.open_session(seed_.principals[static_cast<unsigned>(authenticated)]);
  if(s.boot_session==0){out.error=Error::Core;
  out.core_error=static_cast<unsigned>(robot_boot::Error::Auth);
  return;
  }
  if(w.op==Op::Handoff){if(boot_.status().owner!=s.boot_session||boot_.status().state!=robot_boot::State::Granted){out.error=Error::Denied;
  return;
  }
  if(!mint_handoff()){out.error=Error::Busy;
  if(e.enqueued_at<=std::numeric_limits<Time>::max()-49&&now<e.enqueued_at+49){handoff_waiting_=true;
  handoff_before_=e.enqueued_at+49;
  handoff_generation_=snapshot_.generation;
  }
  }
  return;
  }
  robot_boot::Op op;
  switch(w.op){case Op::Maintenance:op=robot_boot::Op::AcquireMaintenance;
  break;
  case Op::MaintenanceRenew:op=robot_boot::Op::RenewMaintenance;
  break;
  case Op::Unloaded:op=robot_boot::Op::ConfirmUnloaded;
  break;
  case Op::DisableAll:op=robot_boot::Op::DisableAll;
  break;
  case Op::FinishMaintenance:op=robot_boot::Op::FinishMaintenance;
  break;
  case Op::Drive:op=robot_boot::Op::AcquireDrive;
  break;
  case Op::EnableSelected:op=robot_boot::Op::EnableSelected;
  break;
  case Op::Stop:op=robot_boot::Op::Stop;
  break;
  default:out.error=Error::Denied;
  return;
  }
  auto r=boot_.request({profile_.run.gate.boot,s.boot_session,w.seq,w.request,w.lease,op,w.axis,w.unloaded});
  out.lease=r.lease;
  if(r.error==robot_boot::Error::None&&r.lease!=0)s.boot_lease=r.lease;
  if(r.error==robot_boot::Error::None&&w.op==Op::FinishMaintenance)s.boot_lease=0;
  out.core_error=static_cast<unsigned>(r.error);
  if(r.error!=robot_boot::Error::None)out.error=Error::Core;
 }
 else{
  if(s.run_session==0)s.run_session=run_.open_session(seed_.principals[static_cast<unsigned>(authenticated)]);
  if(s.run_session==0){out.error=Error::Core;
  out.core_error=static_cast<unsigned>(robot_gate::Error::BadSession);
  return;
  }
  robot_gate::Op op;
  switch(w.op){case Op::Acquire:op=robot_gate::Op::Acquire;
  break;
  case Op::Renew:op=robot_gate::Op::Renew;
  break;
  case Op::Arm:op=robot_gate::Op::Arm;
  break;
  case Op::Ticket:op=robot_gate::Op::Ticket;
  break;
  case Op::JointStep:
  case Op::Move:op=robot_gate::Op::Move;
  break;
  case Op::Release:op=robot_gate::Op::Release;
  break;
  case Op::Stop:op=robot_gate::Op::Stop;
  break;
  default:out.error=Error::Denied;
  return;
  }
  const robot_gate::Request request{profile_.run.gate.boot,s.run_session,w.seq,w.request,w.lease,w.ticket,op,w.axis,w.direction};
  if(w.op==Op::JointStep&&w.axis!=profile_.run.selected_axis){out.error=Error::Denied;return;}
  auto r=w.op==Op::JointStep?run_.request_joint_step(request,w.joint,{w.radians?robot_joint::StepUnit::CoreRadians:robot_joint::StepUnit::CadDegrees,w.angle}):run_.request(request);
  out.lease=r.lease;
  out.ticket=r.ticket;
  out.core_error=static_cast<unsigned>(r.error);
  if(r.error!=robot_gate::Error::None)out.error=Error::Core;
 }
}
void Owner::tick()noexcept{
 if(!begun_)return;
 // Deliberately independent Stop slot always wins and invalidates queued normal.
 if(pending_[1]){execute(queue_[1],results_[1]);
 result_ready_[1]=true;
 pending_[1]=false;
 if(results_[1].error==Error::None&&(pending_[0]||handoff_waiting_)){results_[0]={};
 results_[0].job=queue_[0].job;
 results_[0].error=Error::Denied;
 result_ready_[0]=true;
 pending_[0]=false;
 handoff_waiting_=false;
 }
 }
 if(pending_[0]){execute(queue_[0],results_[0]);
 result_ready_[0]=!handoff_waiting_;
 pending_[0]=false;
 }
 if(run_active_)run_.poll();
 else boot_.poll();
 publish();
 advance_transfer();
 publish();
 if(handoff_waiting_){const auto now=port_.now_ms();
 if(now>=handoff_before_||snapshot_.generation!=handoff_generation_||boot_.status().state!=robot_boot::State::Granted){handoff_waiting_=false;
 result_ready_[0]=true;
 }
 else if(mint_handoff()){handoff_waiting_=false;
 results_[0].error=Error::None;
 results_[0].accepted_at=port_.now_ms();
 result_ready_[0]=true;
 publish();
 }
 }
}
bool Owner::take_result(Listener l,Time job,Result& out)noexcept{const auto i=slot(l);
if(!result_ready_[i]||results_[i].job!=job)return false;
out=results_[i];
result_ready_[i]=false;
return true;
}
void Owner::publish()noexcept{
 snapshot_.at=port_.now_ms();
 snapshot_.angle_available=false;snapshot_.angle_joint=0;
 snapshot_.paired_mask=0;
 for(unsigned i=0;i<2;++i)if(sessions_[i].paired)snapshot_.paired_mask=static_cast<std::uint8_t>(snapshot_.paired_mask|(1u<<i));
 if(run_active_){const auto s=run_.status();
 const auto g=run_.gate_status();
 snapshot_.core_state=static_cast<unsigned>(s.state);
 snapshot_.core_fault=static_cast<unsigned>(s.fault);
 snapshot_.fault_at=s.fault_at;
 snapshot_.stop_at=s.stop_at;
 snapshot_.stop_verified=s.stop_verified;
 snapshot_.manual_power_cut_required=s.manual_power_cut_required;
 snapshot_.lease_owner=g.owner;
 snapshot_.lease_until=g.lease_until;
 snapshot_.ready=run_.snapshot().ready;
  if(s.state==robot_run::State::Stopping)phase(Phase::Stopping);
  else if(s.state==robot_run::State::Fault||s.state==robot_run::State::StoppedRecheck)phase(Phase::Terminal);
  else if(s.state!=robot_run::State::Checking)phase(Phase::Run);
  const auto angle=run_.joint_step_info(snapshot_.selected_axis);
  if(snapshot_.phase==Phase::Run&&angle.available){snapshot_.angle_available=true;snapshot_.angle_joint=angle.joint;}
  for(unsigned a=0;a<snapshot_.positions.size();++a){auto& p=snapshot_.positions[a];
  p={};
  if(a<snapshot_.axis_count)p.valid=run_.position_sample(a,p.value,p.tx_at,p.at);
  }
  snapshot_.config_oldest_at=run_.oldest_configuration_at();
 }
 else{const auto s=boot_.status();
 snapshot_.core_state=static_cast<unsigned>(s.state);
 snapshot_.core_fault=static_cast<unsigned>(s.error);
 snapshot_.fault_at=s.fault_at;
 snapshot_.stop_at=s.stop_at;
 snapshot_.stop_verified=s.stop_verified;
 snapshot_.manual_power_cut_required=s.manual_power_cut_required;
 snapshot_.lease_owner=s.owner;
 snapshot_.lease_until=s.lease_until;
 snapshot_.ready=false;
  if(s.state==robot_boot::State::Stopping)phase(Phase::Stopping);
  else if(s.state==robot_boot::State::Fault||s.state==robot_boot::State::StoppedRecheck)phase(Phase::Terminal);
  for(unsigned a=0;a<snapshot_.positions.size();++a){auto& p=snapshot_.positions[a];
  p={};
  if(a<snapshot_.axis_count)p.valid=boot_.position_sample(a,p.value,p.tx_at,p.at);
  }
  snapshot_.config_oldest_at=boot_.oldest_configuration_at();
 }
 for(auto& p:snapshot_.positions)p.valid=p.valid&&snapshot_.at>=p.at&&snapshot_.at-p.at<400;
 snapshot_.core_stop_verified=snapshot_.stop_verified;
 if(snapshot_.adapter_fault!=AdapterFault::None){snapshot_.stop_verified=false;
 snapshot_.manual_power_cut_required=true;
 snapshot_.ready=false;
 }
}
} // namespace robot_phone
