#include "robot_boot/supervisor.hpp"
#include <limits>
namespace robot_boot {
bool Supervisor::position_sample(unsigned axis,std::int64_t& value,Time& tx_at,Time& at)const noexcept{value=0;tx_at=at=0;if(profile_.run.gate.count==0||profile_.run.gate.count>proof_.size()||axis>=proof_.size()||axis>=profile_.run.gate.count)return false;const auto& s=proof_[axis].sample[1];value=s.value;tx_at=s.tx;at=s.at;return s.valid;}
Time Supervisor::oldest_configuration_at()const noexcept{if(profile_.run.gate.count==0||profile_.run.gate.count>proof_.size())return 0;Time oldest=~Time{0};for(unsigned a=0;a<profile_.run.gate.count;++a)for(const auto& s:proof_[a].config){if(!s.valid)return 0;if(s.at<oldest)oldest=s.at;}return oldest==~Time{0}?0:oldest;}
using namespace robot_can;
namespace {constexpr Time max=std::numeric_limits<Time>::max();constexpr std::array<std::uint8_t,4> diagnostic{0xF1,0x31,0x32,0x3A};}
Supervisor::Supervisor(CanPort& p,const Profile& cfg)noexcept:port_(p),profile_(cfg),stop_link_(p){}
bool Supervisor::active()const noexcept{return status_.state!=State::Idle&&status_.state!=State::HandedOff&&status_.state!=State::Stopping&&status_.state!=State::StoppedRecheck&&status_.state!=State::Fault;}
bool Supervisor::add(Time d,Time& out)noexcept{const auto now=port_.now_ms();if(now>max-d){fail(Error::Time);return false;}out=now+d;return true;}
Time Supervisor::id()noexcept{if(next_id_==max){fail(Error::Exhausted);return 0;}return next_id_++;}
unsigned Supervisor::expected(unsigned a,unsigned c)const noexcept{switch(c){case 0:return 5;case 1:return 16;case 2:return 2;case 3:return profile_.run.gate.axes[a];case 4:return 0x101;case 5:return 0;default:return 1000;}}
bool Supervisor::fresh(const Evidence& e,Time ttl)const noexcept{const auto now=port_.now_ms();return e.valid&&now>=e.at&&now-e.at<ttl;}
bool Supervisor::configs()const noexcept{for(unsigned a=0;a<profile_.run.gate.count;++a)for(unsigned c=0;c<7;++c)if(!fresh(proof_[a].config[c],4000))return false;return true;}
bool Supervisor::stopped()const noexcept{
 for(unsigned a=0;a<profile_.run.gate.count;++a){const auto& p=proof_[a];for(const auto& s:p.sample)if(!fresh(s,400))return false;if(p.sample[0].value!=1||p.sample[2].value!=0||p.count!=3)return false;
 auto lo=p.positions[0].value,hi=lo;for(unsigned i=0;i<3;++i){const auto& s=p.positions[i];if(!fresh(s,400)||(i&&(s.tx<p.positions[i-1].tx||s.tx-p.positions[i-1].tx<140)))return false;if(s.value<lo)lo=s.value;if(s.value>hi)hi=s.value;}if(static_cast<Time>(hi-lo)>profile_.run.stop.tolerance_counts)return false;}
 return true;
}
bool Supervisor::mask(bool selected)const noexcept{for(unsigned a=0;a<profile_.run.gate.count;++a){const bool on=selected&&profile_.run.gate.axes[a]==profile_.run.selected_axis;if(!fresh(proof_[a].sample[3],400)||proof_[a].sample[3].value!=(on?1:0))return false;}return true;}
bool Supervisor::claim()const noexcept{return maintenance_&&status_.owner!=0&&port_.now_ms()<unloaded_until_&&port_.now_ms()<status_.lease_until;}
bool Supervisor::eligible_stop()const noexcept{return !premise_lost_&&heartbeat_mask_==((1u<<profile_.run.gate.count)-1)&&profile_.run.stop.response_bounds_approved&&profile_.run.stop.position_tolerance_approved;}
void Supervisor::record_fault(Error error,Time at)noexcept{
 if(!stop_fault_){status_.error=error;status_.fault_at=at;stop_fault_=true;}
}
void Supervisor::abort_stop(Error error)noexcept{
 record_fault(error,port_.now_ms());status_.state=State::Fault;status_.stop_verified=false;
 status_.closed=stop_link_.close_attempted()?stop_link_.close_result():port_.close();
 status_.manual_power_cut_required=status_.torque_unknown=true;
}
void Supervisor::stop_poll(bool first)noexcept{
 const auto before=port_.now_ms();if(before<last_clock_||before>=stop_until_||(!prep_seen_&&before>=prep_until_)||(first&&(before-status_.stop_at>=10||before>=isolate_until_))){abort_stop(Error::Time);return;}
 last_clock_=before;if(first){auto p=profile_.run.stop;p.heartbeat_1000_readback_confirmed=true;stop_link_.begin_stop(p);}else stop_link_.poll();const auto now=port_.now_ms();
 if(now<before||now-before>=10||now>=stop_until_||(first&&now>=isolate_until_)){abort_stop(Error::Time);return;}last_clock_=now;
 const auto phase=stop_link_.core().state();const bool past=phase==robot_core::StopState::Quiet||phase==robot_core::StopState::Verifying||phase==robot_core::StopState::StoppedRecheck;
 if(!prep_seen_&&past){if(now>=prep_until_){abort_stop(Error::Time);return;}prep_seen_=true;}
 if(stop_link_.state()==LinkState::Fault){abort_stop(Error::Port);return;}
 if(stop_link_.state()==LinkState::StoppedRecheck){status_.closed=stop_link_.close_result();status_.stop_verified=prep_seen_&&status_.closed.healthy&&status_.closed.quiesced;if(!status_.stop_verified){abort_stop(Error::Cleanup);return;}status_.state=stop_fault_?State::Fault:State::StoppedRecheck;status_.manual_power_cut_required=false;}
}
void Supervisor::stop(Error e,bool fault)noexcept{
 if(!active())return;
 status_.stop_at=port_.now_ms();if(fault)record_fault(e,status_.stop_at);status_.state=State::Stopping;pending_={};inflight_=false;status_.owner=lease_=0;unloaded_until_=0;status_.torque_unknown=true;
 if(!eligible_stop()||status_.stop_at>max-3600){record_fault(status_.stop_at>max-3600?Error::Time:(e==Error::None?Error::Proof:e),status_.stop_at);if(touched_)status_.closed=port_.close();status_.state=State::Fault;status_.manual_power_cut_required=true;return;}
 stop_until_=status_.stop_at+3600;prep_until_=status_.stop_at+600;isolate_until_=status_.stop_at+100;stop_poll(true);
}
void Supervisor::fail(Error e,bool lost)noexcept{premise_lost_=premise_lost_||lost;stop(e,true);}
bool Supervisor::advance()noexcept{
 if(!active())return false;
 const auto now=port_.now_ms();if(now<last_clock_){fail(Error::Clock);return false;}if(now<operation_at_||now-operation_at_>=10){fail(Error::Time);return false;}last_clock_=now;
 if(status_.owner!=0&&now>=status_.lease_until){stop(Error::Lease,false);return false;}
 if((status_.state==State::ReadConfig||status_.state==State::Disabling||status_.state==State::Heartbeat||status_.state==State::Enabling)&&now>=phase_until_){fail(Error::Time);return false;}
 if(inflight_&&now>=tx_until_){fail(Error::Time);return false;}if(pending_.active&&pending_.confirmed&&now>=pending_.deadline){fail(Error::Time);return false;}
 if(status_.owner!=0){if(!configs()){fail(Error::Proof);return false;}for(unsigned a=0;a<profile_.run.gate.count;++a)for(const auto& s:proof_[a].sample)if(!fresh(s,400)){fail(Error::Proof);return false;}}
 if(status_.state==State::Disabling&&!claim()){fail(Error::Lease);return false;}return true;
}
void Supervisor::begin()noexcept{
 if(begun_)return;
 begun_=true;const auto& p=profile_.run;const auto& c=p.gate;robot_gate::ControlGate check(c);bool selected=false;for(unsigned a=0;a<c.count&&a<2;++a)if(c.axes[a]==p.selected_axis)selected=true;
 if(check.status().fault||!profile_.hardware_identity_approved||!p.normal_approved||!p.stop.response_bounds_approved||!p.stop.position_tolerance_approved||p.stop.axis_count!=c.count||p.enable_policy!=robot_run::EnablePolicy::SingleSelected||!selected||p.counts_per_100pulse==0||p.counts_per_100pulse>(Time{1}<<40)||p.stop.tolerance_counts>(Time{1}<<32)||(p.dir0_sign!=1&&p.dir0_sign!=-1)){status_.state=State::Fault;record_fault(Error::Profile,port_.now_ms());return;}
 for(unsigned a=0;a<c.count;++a)if(c.axes[a]!=p.stop.axes[a]){status_.state=State::Fault;record_fault(Error::Profile,port_.now_ms());return;}
 status_.state=State::ReadConfig;last_clock_=last_poll_=operation_at_=port_.now_ms();if(!add(3000,phase_until_))return;touched_=true;if(!port_.reset_and_start()){fail(Error::Port);return;}advance();next_send_=port_.now_ms();
}
bool Supervisor::health(bool empty)noexcept{
 std::uint32_t alerts=0;PortStatus s;if(!port_.read_alerts(alerts)||!port_.status(s)){fail(Error::Port);return false;}if(!advance())return false;
 if(s.state!=BusState::Running||!error_counters_clear(s)||(alerts&fatal_alerts)||(alerts&~all_alerts)){fail(Error::Port,true);return false;}if(s.rx_pending>16||(empty&&s.rx_pending!=0)){fail(Error::Port);return false;}if(s.tx_pending>1||(s.tx_pending!=0&&!inflight_)){fail(Error::Protocol);return false;}
 const auto terminal=alerts&(TxSuccess|TxFailed);if(terminal){if(!inflight_||s.tx_pending!=0||terminal!=TxSuccess){fail(Error::Protocol);return false;}inflight_=false;pending_.confirmed=true;pending_.tx=port_.now_ms();const bool write=pending_.kind==Kind::Disable||pending_.kind==Kind::Enable||pending_.kind==Kind::Heartbeat;
 if(pending_.kind==Kind::Config)last_[pending_.axis][4+pending_.index]=pending_.tx;else if(pending_.kind==Kind::Diag)last_[pending_.axis][pending_.index]=pending_.tx;else if(pending_.kind==Kind::Heartbeat)last_[pending_.axis][10]=pending_.tx;
 if(!add(write?200:100,pending_.deadline))return false;}
 return true;
}
bool Supervisor::send(const robot_core::mks::EncodeResult& f,Kind kind,unsigned a,unsigned index)noexcept{
 if(!f.ok()){fail(Error::Protocol);return false;}if(!health(true)||!advance())return false;Time before;if(!add(50,before))return false;pending_={true,false,kind,a,index,0,0};inflight_=true;tx_until_=before;
 WireFrame wire{f.frame.id,f.frame.dlc,f.frame.data,f.frame.extended,f.frame.rtr};if(!port_.submit(wire,before)){fail(Error::Port);return false;}if(!advance())return false;if(port_.now_ms()>=before){fail(Error::Time);return false;}if(!add(20,next_send_))return false;return true;
}
void Supervisor::receive(const RxFrame& rx)noexcept{
 raw_[raw_head_]=rx;raw_head_=(raw_head_+1)%raw_.size();if(!advance())return;if(!pending_.active||!pending_.confirmed||rx.frame.id!=profile_.run.gate.axes[pending_.axis]||rx.frame.id>0x7FF||rx.dequeued_at<pending_.tx||rx.dequeued_at>=pending_.deadline||rx.dequeued_at>port_.now_ms()||port_.now_ms()-rx.dequeued_at>=10)return;
 robot_core::mks::Frame f{static_cast<std::uint16_t>(rx.frame.id),rx.frame.dlc,rx.frame.data,rx.frame.extended,rx.frame.rtr};const auto current=pending_;auto& a=proof_[current.axis];
 if(current.kind==Kind::Config){const auto value=parse_config(f,settings[current.index]);if(value.error==DecodeError::Unsupported){fail(Error::Config,true);return;}if(value.error!=DecodeError::None)return;
  if((current.index!=6||((heartbeat_mask_>>current.axis)&1u))&&value.value!=expected(current.axis,current.index)){fail(Error::Config,true);return;}
  a.config[current.index]={true,value.value,current.tx,rx.dequeued_at};pending_={};
  if(status_.state==State::ReadConfig){++config_cursor_;if(config_cursor_==7*profile_.run.gate.count){status_.state=State::Observe;add(2000,phase_until_);}}
  if(status_.state==State::Heartbeat&&await_readback_&&current.axis==target_&&current.index==6&&current.tx>torque_ack_){if(value.value!=1000){fail(Error::Config,true);return;}heartbeat_mask_|=1u<<target_;await_readback_=false;++target_;if(target_==profile_.run.gate.count){status_.heartbeat_verified=true;maintenance_done_=true;status_.state=stopped()&&mask(false)?State::ReadyDisabled:State::Observe;}}
 }else if(current.kind==Kind::Heartbeat){if(!parse_heartbeat_ack(f))return;pending_={};await_readback_=true;torque_ack_=port_.now_ms();}
 else if(current.kind==Kind::Disable||current.kind==Kind::Enable){const auto value=robot_core::mks::parse_response(f);if(!value.ok()||value.parsed.code!=0xF3)return;if(value.parsed.value!=1){fail(Error::Protocol);return;}pending_={};await_readback_=true;torque_ack_=port_.now_ms();}
 else {const auto value=robot_core::mks::parse_response(f);if(!value.ok()||value.parsed.code!=diagnostic[current.index])return;a.sample[current.index]={true,value.parsed.value,current.tx,rx.dequeued_at};pending_={};
  if(current.index==1){if(a.count<3)a.positions[a.count++]=a.sample[1];else{a.positions[0]=a.positions[1];a.positions[1]=a.positions[2];a.positions[2]=a.sample[1];}}
  if(status_.owner!=0&&((current.index==0&&value.parsed.value!=1)||(current.index==2&&value.parsed.value!=0))){fail(Error::Proof);return;}
  if((status_.state==State::Enabling||status_.state==State::Granted)&&current.index==3&&profile_.run.gate.axes[current.axis]!=profile_.run.selected_axis&&value.parsed.value!=0){fail(Error::Proof);return;}
  if(await_readback_&&(status_.state==State::Disabling||status_.state==State::Enabling)&&current.axis==target_&&current.index==3&&current.tx>torque_ack_){const auto want=status_.state==State::Disabling?0:1;if(value.parsed.value!=want){fail(Error::Proof);return;}await_readback_=false;if(want==0){disabled_mask_|=1u<<target_;++target_;if(target_==profile_.run.gate.count){status_.state=State::Observe;for(auto& pr:proof_)pr.count=0;}}else{status_.state=State::Granted;for(auto& pr:proof_)pr.count=0;}}
 }
 if(!active())return;
 if((status_.state==State::Observe||status_.state==State::NeedsMaintenance)&&stopped()){
  if(disabled_mask_==((1u<<profile_.run.gate.count)-1)&&!maintenance_done_){status_.state=State::Heartbeat;target_=0;await_readback_=false;}
  else status_.state=mask(false)?State::ReadyDisabled:State::NeedsMaintenance;
 }
}
void Supervisor::schedule()noexcept{
 if(!advance()||pending_.active||inflight_||port_.now_ms()<next_send_)return;
 const auto now=port_.now_ms();const auto count=profile_.run.gate.count;
 auto read=[&](unsigned a,unsigned index,bool config){const auto prev=last_[a][config?index+4:index];if(prev!=0&&(now<prev||now-prev<140))return false;return send(config?read_config(profile_.run.gate.axes[a],settings[index]):robot_core::mks::build_read(profile_.run.gate.axes[a],diagnostic[index]),config?Kind::Config:Kind::Diag,a,index);};
 if(status_.state==State::ReadConfig){read(config_cursor_%count,config_cursor_/count,true);return;}
 if(status_.state==State::Disabling||status_.state==State::Enabling){if(!await_readback_){if(!configs()||(status_.state==State::Disabling&&!claim())){fail(Error::Proof);return;}if(stopped()){send(robot_core::mks::build_enable(profile_.run.gate.axes[target_],status_.state==State::Enabling),status_.state==State::Enabling?Kind::Enable:Kind::Disable,target_,0);return;}}else if(read(target_,3,false))return;}
 if(status_.state==State::Heartbeat){if(!await_readback_){if(!mask(false)){fail(Error::Proof);return;}if(stopped()){send(heartbeat1000(profile_.run.gate.axes[target_]),Kind::Heartbeat,target_,6);return;}}else if(read(target_,6,true))return;}
 if(need_config_){const auto a=refresh_cursor_%count,c=refresh_cursor_/count;if(read(a,c,true)){refresh_cursor_=(refresh_cursor_+1)%(count*7);need_config_=false;return;}}
 if(read(diag_cursor_%count,diag_cursor_/count,false)){diag_cursor_=(diag_cursor_+1)%(count*4);if(diag_cursor_==0)need_config_=true;}
}
void Supervisor::poll()noexcept{
 if(status_.state==State::Stopping){stop_poll(false);return;}if(!active())return;const auto now=port_.now_ms();operation_at_=now;if(now<last_poll_||now-last_poll_>=10){fail(Error::Time);return;}last_poll_=now;
 if(!advance()||!health())return;
 for(unsigned i=0;i<16;++i){RxFrame r;const auto result=port_.receive(r);if(result==ReceiveResult::Error){fail(Error::Port);return;}if(!advance())return;if(result==ReceiveResult::Empty)break;if(!health())return;receive(r);if(!active())return;}
 if(!health(true)||!advance())return;
 if(status_.state==State::Observe&&port_.now_ms()>=phase_until_){fail(Error::Proof);return;}schedule();if(active())health();
}
Time Supervisor::open_session(Time who)noexcept{operation_at_=port_.now_ms();if(who==0||!advance())return 0;for(auto& s:sessions_)if(s.id==0){s={id(),who,0,0};return s.id;}return 0;}
Result Supervisor::request(const Request& r)noexcept{
 operation_at_=port_.now_ms();if(!advance())return{Error::Denied,0};if(r.boot!=profile_.run.gate.boot)return{Error::Auth,0};Session* session=nullptr;for(auto& s:sessions_)if(s.id==r.session&&r.session!=0)session=&s;if(!session)return{Error::Auth,0};if(r.op==Op::Stop){stop(Error::None,false);return{};}
 if(r.seq==0||r.request==0||r.seq<=session->seq||r.request<=session->request)return{Error::Replay,0};
 if(r.seq==max||r.request==max){fail(Error::Exhausted);return{Error::Exhausted,0};}session->seq=r.seq;session->request=r.request;
 if(static_cast<unsigned>(r.op)>static_cast<unsigned>(Op::Stop))return{Error::Denied,0};
 if(r.op==Op::AcquireMaintenance||r.op==Op::AcquireDrive){if(status_.owner!=0)return{Error::Busy,0};if(!configs()||!stopped())return{Error::Proof,0};if(r.op==Op::AcquireDrive&&(!finished_||!maintenance_done_||!mask(false)||!status_.heartbeat_verified))return{Error::Denied,0};status_.owner=r.session;principal_=session->principal;lease_=id();maintenance_=r.op==Op::AcquireMaintenance;if(!add(800,status_.lease_until))return{Error::Time,0};return{Error::None,lease_};}
 if(r.session!=status_.owner||r.lease==0||r.lease!=lease_)return{Error::Lease,0};
 if(r.op==Op::RenewMaintenance){if(!add(800,status_.lease_until))return{Error::Time,0};return{Error::None,lease_};}
 if(r.op==Op::ConfirmUnloaded){if(!maintenance_||!r.unloaded_confirmed)return{Error::Denied,0};Time end;if(!add(800,end))return{Error::Time,0};unloaded_until_=end<status_.lease_until?end:status_.lease_until;return{Error::None,lease_};}
 if(r.op==Op::DisableAll){if((status_.state!=State::NeedsMaintenance&&status_.state!=State::ReadyDisabled)||pending_.active||inflight_||await_readback_)return{Error::Busy,0};if(!maintenance_||!claim()||!stopped()||!configs())return{Error::Proof,0};if(pending_.active||inflight_)return{Error::Busy,0};status_.state=State::Disabling;target_=disabled_mask_=0;await_readback_=false;if(!add(2500,phase_until_))return{Error::Time,0};return{Error::None,lease_};}
 if(r.op==Op::FinishMaintenance){if(status_.state!=State::ReadyDisabled||pending_.active||inflight_||await_readback_)return{Error::Busy,0};if(!maintenance_||!maintenance_done_||!stopped()||!mask(false))return{Error::Denied,0};status_.owner=lease_=0;status_.lease_until=unloaded_until_=0;maintenance_=false;finished_=true;return{};}
 if(r.op==Op::EnableSelected){if(maintenance_||!finished_||r.axis!=profile_.run.selected_axis||status_.state!=State::ReadyDisabled||!stopped()||!mask(false)||!configs())return{Error::Proof,0};if(pending_.active||inflight_)return{Error::Busy,0};target_=r.axis==profile_.run.gate.axes[0]?0:1;await_readback_=false;status_.state=State::Enabling;if(!add(1000,phase_until_))return{Error::Time,0};return{Error::None,lease_};}
 return{Error::Denied,0};
}
bool Supervisor::take_evidence(robot_run::BootEvidence& out)noexcept{
 operation_at_=port_.now_ms();if(!advance()||status_.state!=State::Granted||!stopped()||!mask(true)||!configs()||!status_.heartbeat_verified||pending_.active||inflight_)return false;
 if(!health(true))return false;
 Time admit;if(!add(50,admit))return false;Time config=max;
 for(unsigned a=0;a<profile_.run.gate.count;++a){for(const auto& e:proof_[a].sample){if(e.at>max-400){fail(Error::Time);return false;}const auto expiry=e.at+400;if(expiry<admit)admit=expiry;}for(const auto& e:proof_[a].config){if(e.at>max-4000){fail(Error::Time);return false;}const auto expiry=e.at+4000;if(expiry<config)config=expiry;}}
 if(status_.lease_until<admit)admit=status_.lease_until;
 status_.closed=port_.close();if(!advance()||!status_.closed.healthy||!status_.closed.quiesced){fail(Error::Cleanup);return false;}
 if(port_.now_ms()>=admit||port_.now_ms()>=config){fail(Error::Time);return false;}
 for(unsigned a=0;a<profile_.run.gate.count;++a)for(unsigned c=0;c<7;++c){const auto& sample=proof_[a].config[c];out.settings_[a][c]={sample.valid,static_cast<std::uint32_t>(sample.value),sample.tx,sample.at};}
 out.port_=&port_;out.profile_=profile_.run;out.profile_.stop.heartbeat_1000_readback_confirmed=true;out.principal_=principal_;out.admit_=admit;out.config_=config;out.authority_=status_.lease_until;out.valid_=true;status_.state=State::HandedOff;return true;
}
} // namespace robot_boot
