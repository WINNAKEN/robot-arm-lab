#include "angle_fixture.inc"
static void publish(const AngleFixture& f){
 const auto s=f.owner.snapshot();
 std::cout<<"{\"boot\":\"11\",\"generation\":\""<<s.generation<<"\",\"at\":\""<<s.at
  <<"\",\"lease_owner\":\""<<s.lease_owner<<"\",\"lease_until\":\""<<s.lease_until
  <<"\",\"config_oldest_at\":\""<<s.config_oldest_at<<"\",\"fault_at\":\""<<s.fault_at<<"\",\"stop_at\":\""<<s.stop_at
  <<"\",\"phase\":"<<unsigned(s.phase)<<",\"core_state\":"<<s.core_state<<",\"core_fault\":"<<s.core_fault
  <<",\"adapter_fault\":"<<unsigned(s.adapter_fault)<<",\"ready\":"<<(s.ready?"true":"false")
  <<",\"selected_axis\":"<<s.selected_axis<<",\"axis_count\":"<<unsigned(s.axis_count)
  <<",\"angle_available\":"<<(s.angle_available?"true":"false")<<",\"angle_joint\":"<<s.angle_joint
  <<",\"stop_verified\":"<<(s.stop_verified?"true":"false")<<",\"core_stop_verified\":"<<(s.core_stop_verified?"true":"false")
  <<",\"manual_power_cut_required\":"<<(s.manual_power_cut_required?"true":"false")<<",\"queue_stop_late\":"<<(s.queue_stop_late?"true":"false")<<",\"positions\":[";
 for(unsigned i=0;i<s.positions.size();++i){const auto& p=s.positions[i];if(i)std::cout<<",";std::cout<<"{\"valid\":"<<(p.valid?"true":"false")<<",\"value\":\""<<p.value<<"\",\"tx_at\":\""<<p.tx_at<<"\",\"at\":\""<<p.at<<"\"}";}
 std::cout<<"]}"<<std::endl;
}
#include "../phone_transfer/test_transfer.inc"
int main(int argc,char** argv){
 if(argc==2&&std::strcmp(argv[1],"--test")==0)return transfer_tests();if(argc!=2)return 2;AngleFixture f(1,std::strcmp(argv[1],"true")==0);
 f.state(static_cast<unsigned>(robot_boot::State::NeedsMaintenance));
 CHECK(!f.renewing);std::string line;
 while(std::getline(std::cin,line)){
  if(line=="P"){publish(f);continue;}
  if(line.rfind("W ",0)==0){const auto target=std::stoull(line.substr(2));if(target>f.p.now+60000)return 3;while(f.p.now<target)f.step();std::cout<<"{\"at\":\""<<f.p.now<<"\"}"<<std::endl;continue;}
  if(line=="M"){
   bool slot=f.p.ps.tx_pending==0&&f.p.size==0;Time margin=400;
   for(unsigned a=0;a<2;++a){std::array<Time,3> times{};unsigned count=0;
    for(unsigned i=0;i<f.p.sent_count;++i){const auto& t=f.p.sent[i];if(t.frame.id==a+1&&t.frame.data[0]==0x31&&t.at<=f.p.received_diag[a][1]){if(count<3)times[count++]=t.at;else{times[0]=times[1];times[1]=times[2];times[2]=t.at;}}}
    slot=slot&&count==3&&times[1]>=times[0]+140&&times[2]>=times[1]+140;
    for(const auto at:times){if(f.p.now<at||f.p.now-at>=400)slot=false;else if(400-(f.p.now-at)<margin)margin=400-(f.p.now-at);}
    for(const auto at:f.p.received_diag[a]){if(!at||f.p.now<at||f.p.now-at>=400)slot=false;else if(400-(f.p.now-at)<margin)margin=400-(f.p.now-at);}
   }
   const auto pos=f.p.received_diag[0][1];const bool soon=pos&&f.p.now>=pos&&f.p.now-pos<12&&f.p.now-f.p.received_diag[1][1]>=140;
   std::cout<<"{\"moves\":"<<f.p.moves<<",\"transfer_attempts\":"<<f.owner.transfer_attempts()<<",\"violations\":"<<f.p.violations<<",\"confirm_phase\":"<<(soon?"true":"false")<<",\"operator_slot\":"<<(slot&&margin>=12?"true":"false")<<",\"margin_ms\":"<<margin<<",\"at\":\""<<f.p.now<<"\",\"fd\":[";bool comma=false;
   for(unsigned i=0;i<f.p.sent_count;++i){const auto& raw=f.p.sent[i].frame;if(raw.data[0]!=0xFD)continue;if(comma)std::cout<<",";comma=true;std::cout<<"{\"axis\":"<<raw.id<<",\"direction\":"<<((raw.data[1]&0x80)?1:0)<<",\"pulses\":"<<unsigned(raw.data[6])<<"}";}
   std::cout<<"]}"<<std::endl;continue;
  }
  if(line.rfind("C ",0)==0||line.rfind("A ",0)==0){const bool auth=line[0]=='A';if(auth&&line.size()<35)return 4;phone::Wire w;if(!phone::parse(line.substr(auth?35:2),w)){std::cout<<"{\"wire_error\":1,\"core_error\":0}"<<std::endl;continue;}
   phone::Envelope e;e.wire=w;e.listener=w.op==phone::Op::Stop?phone::Listener::Stop:phone::Listener::Normal;e.credential=f.credential;if(auth)for(unsigned i=0;i<32;++i)e.credential[i]=line[2+i];const auto r=f.transact(e);std::cout<<"{\"wire_error\":"<<unsigned(r.error)<<",\"core_error\":"<<r.core_error<<",\"lease\":\""<<r.lease<<"\",\"ticket\":\""<<r.ticket<<"\",\"accepted_at\":\""<<r.accepted_at<<"\",\"transfer_id\":\""<<r.transfer_id<<"\",\"transfer_state\":"<<unsigned(r.transfer_state)<<",\"transfer_generation\":\""<<r.transfer_generation<<"\",\"pending_until\":\""<<r.pending_until<<"\",\"grant_at\":\""<<r.grant_at<<"\",\"lease_until\":\""<<r.lease_until<<"\",\"sequence_floor\":\""<<r.sequence_floor<<"\",\"queued\":true}"<<std::endl;continue;
  }
  return 4;
 }
 return 0;
}
