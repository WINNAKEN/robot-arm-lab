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
