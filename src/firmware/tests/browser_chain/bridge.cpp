#define ROBOT_BOOT_FIXTURE_ONLY
#include "../boot/test_boot.cpp"
#include "robot_phone/owner.hpp"
#include <string>
#include <iostream>
#include <cstring>
namespace phone=robot_phone;
phone::Secret secret(char c){phone::Secret s{};for(unsigned i=0;i<32;++i)s[i]=c;return s;}
phone::Seed seed(){phone::Seed s;s.boot=11;s.pairing=secret('a');s.credentials={secret('b'),secret('c')};s.principals={101,202};return s;}
struct Bench {
 BootFake p;robot_boot::Profile profile;std::array<robot_joint::Calibration,2> calibration{};phone::Owner owner;
 explicit Bench(unsigned axis):profile(boot_profile(axis)),owner(p,profile,seed(),calibration){owner.begin();}
 void step(){++p.now;owner.tick();}
};
static void result(const phone::Result& r){
 std::cout<<"{\"ready\":true,\"queued\":true,\"job\":\""<<r.job<<"\",\"wire_error\":"<<unsigned(r.error)<<",\"core_error\":"<<r.core_error<<",\"paired\":"<<(r.paired?"true":"false")<<",\"credential\":\""<<(r.paired?std::string(r.credential.data(),32):std::string())<<"\",\"lease\":\""<<r.lease<<"\",\"ticket\":\""<<r.ticket<<"\",\"accepted_at\":\""<<r.accepted_at<<"\",\"transfer_id\":\""<<r.transfer_id<<"\",\"transfer_state\":"<<unsigned(r.transfer_state)<<",\"transfer_generation\":\""<<r.transfer_generation<<"\",\"pending_until\":\""<<r.pending_until<<"\",\"grant_at\":\""<<r.grant_at<<"\",\"lease_until\":\""<<r.lease_until<<"\",\"sequence_floor\":\""<<r.sequence_floor<<"\"}"<<std::endl;
}
static void publish(const Bench& f){
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
int main(int argc,char** argv){
 if(argc!=2)return 2;const auto axis=static_cast<unsigned>(std::stoul(argv[1]));if(axis<1||axis>2)return 2;Bench f(axis);Time job=0;std::string line;
 while(std::getline(std::cin,line)){
  if(line=="P"){publish(f);continue;}
  if(line.rfind("W ",0)==0){const Time target=std::stoull(line.substr(2));if(target<f.p.now||target-f.p.now>60000)return 3;while(f.p.now<target)f.step();std::cout<<"{\"at\":\""<<f.p.now<<"\"}"<<std::endl;continue;}
  if(line=="M"||line=="F"){
   bool slot=f.p.ps.tx_pending==0&&f.p.size==0;Time margin=400;
   for(unsigned a=0;a<2;++a){std::array<Time,3> times{};unsigned count=0;
    for(unsigned i=0;i<f.p.sent_count;++i){const auto& t=f.p.sent[i];if(t.frame.id==a+1&&t.frame.data[0]==0x31&&t.at<=f.p.received_diag[a][1]){if(count<3)times[count++]=t.at;else{times[0]=times[1];times[1]=times[2];times[2]=t.at;}}}
    slot=slot&&count==3&&times[1]>=times[0]+140&&times[2]>=times[1]+140;
    for(const auto t:times){if(f.p.now<t||f.p.now-t>=400)slot=false;else if(400-(f.p.now-t)<margin)margin=400-(f.p.now-t);}
    for(const auto t:f.p.received_diag[a]){if(!t||f.p.now<t||f.p.now-t>=400)slot=false;else if(400-(f.p.now-t)<margin)margin=400-(f.p.now-t);}
   }
   std::cout<<"{\"at\":\""<<f.p.now<<"\",\"moves\":"<<f.p.moves<<",\"transfer_attempts\":"<<f.owner.transfer_attempts()<<",\"operator_slot\":"<<(slot&&margin>=12?"true":"false")<<",\"margin\":"<<margin<<",\"paired_mask\":"<<unsigned(f.owner.snapshot().paired_mask)<<",\"calibration_measured\":"<<((f.calibration[0].measured||f.calibration[1].measured)?"true":"false")<<",\"frames\":[";
   for(unsigned i=0;line=="F"&&i<f.p.sent_count;++i){if(i)std::cout<<",";const auto& r=f.p.sent[i];std::cout<<"{\"at\":\""<<r.at<<"\",\"axis\":"<<r.frame.id<<",\"data\":[";for(unsigned j=0;j<r.frame.dlc;++j){if(j)std::cout<<",";std::cout<<unsigned(r.frame.data[j]);}std::cout<<"]}";}
   std::cout<<"]}"<<std::endl;continue;
  }
  if(line.rfind("R ",0)==0){if(line.size()<5)return 4;const auto listener=line[2]=='X'?phone::Listener::Stop:phone::Listener::Normal;phone::Result r;if(f.owner.take_result(listener,std::stoull(line.substr(4)),r))result(r);else std::cout<<"{\"ready\":false}"<<std::endl;continue;}
  if(line.size()>=34&&(line[0]=='J'||line[0]=='N'||line[0]=='X')&&line[1]==' '){
   phone::Envelope e;e.job=++job;e.listener=line[0]=='X'?phone::Listener::Stop:phone::Listener::Normal;e.pairing=line[0]=='J';for(unsigned i=0;i<32;++i)e.credential[i]=line[2+i];
   if(e.pairing)e.enqueued_at=f.p.now;
   else{if(line.size()<37)return 4;const auto split=line.find(' ',35);if(split==std::string::npos)return 4;e.enqueued_at=std::stoull(line.substr(35,split-35));if(!phone::parse(line.substr(split+1),e.wire)){std::cout<<"{\"ready\":true,\"wire_error\":1,\"core_error\":0}"<<std::endl;continue;}}
   const auto before=f.p.now;if(!f.owner.enqueue(e)){std::cout<<"{\"ready\":true,\"queued\":false,\"wire_error\":"<<unsigned(phone::Error::Busy)<<",\"core_error\":0}"<<std::endl;continue;}f.owner.tick();if(f.p.now!=before)return 5;
   phone::Result r;if(f.owner.take_result(e.listener,e.job,r))result(r);else std::cout<<"{\"ready\":false,\"job\":\""<<e.job<<"\"}"<<std::endl;continue;
  }
  return 4;
 }
 return 0;
}
