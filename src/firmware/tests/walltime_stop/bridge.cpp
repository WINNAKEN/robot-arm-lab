// Reuse the exact existing fake bench + production result/status serializers.
#include "common.inc"
#include <chrono>
#include <thread>
#include <mutex>
#include <deque>
#define NOMINMAX
#include <windows.h>

using Clock=std::chrono::steady_clock;
struct Input {std::string line;Time at;};
struct Audit {
 Time ticks{0},gap{0},previous{0},received{0},dispatch{0},pre_stop{0},accepted{0},post_stop{0};
 unsigned pre_phase{0},pre_fault{0},pre_adapter{0};
};

static void handle(Bench& f, const Input& input, Time& job, Audit& a){
 const auto& line=input.line;
 if(line=="P"){publish(f);return;}
 if(line=="T"){
  std::cout<<"{\"wait_primitive\":\"windows_high_resolution_waitable_1ms\",\"at\":"<<f.p.now<<",\"ticks\":"<<a.ticks<<",\"max_gap\":"<<a.gap
   <<",\"received\":"<<a.received<<",\"dispatch\":"<<a.dispatch<<",\"pre_stop\":"<<a.pre_stop
   <<",\"pre_phase\":"<<a.pre_phase<<",\"pre_fault\":"<<a.pre_fault<<",\"pre_adapter\":"<<a.pre_adapter
   <<",\"accepted\":"<<a.accepted<<",\"post_stop\":"<<a.post_stop<<"}"<<std::endl;return;
 }
 #include "metrics.inc"
 if(line.rfind("W ",0)==0)std::quick_exit(3); // No clock control entry.
 if(line.rfind("R ",0)==0){
  if(line.size()<5)std::quick_exit(4);
  const auto listener=line[2]=='X'?phone::Listener::Stop:phone::Listener::Normal;
  phone::Result r;
  if(f.owner.take_result(listener,std::stoull(line.substr(4)),r))result(r);
  else std::cout<<"{\"ready\":false}"<<std::endl;
  return;
 }
 if(line.size()<34||(line[0]!='J'&&line[0]!='N'&&line[0]!='X')||line[1]!=' ')std::quick_exit(4);
 phone::Envelope e;e.job=++job;e.listener=line[0]=='X'?phone::Listener::Stop:phone::Listener::Normal;e.pairing=line[0]=='J';
 for(unsigned i=0;i<32;++i)e.credential[i]=line[2+i];
 e.enqueued_at=input.at; // Actual steady-clock stdin reader receipt, never caller time.
 if(!e.pairing){
  if(line.size()<37)std::quick_exit(4);
  const auto split=line.find(' ',35);if(split==std::string::npos)std::quick_exit(4);
  if(line.substr(35,split-35)!="0")std::quick_exit(4); // Wire compatibility placeholder only.
  if(!phone::parse(line.substr(split+1),e.wire)){
   std::cout<<"{\"ready\":true,\"wire_error\":1,\"core_error\":0}"<<std::endl;return;
  }
 }
 const auto pre=f.owner.snapshot();a.received=input.at;a.dispatch=f.p.now;a.pre_stop=pre.stop_at;
 a.pre_phase=static_cast<unsigned>(pre.phase);a.pre_fault=pre.core_fault;a.pre_adapter=static_cast<unsigned>(pre.adapter_fault);a.accepted=0;
 if(!f.owner.enqueue(e)){
  std::cout<<"{\"ready\":true,\"queued\":false,\"wire_error\":"<<unsigned(phone::Error::Busy)<<",\"core_error\":0}"<<std::endl;return;
 }
 f.owner.tick();phone::Result r;
 const bool ready=f.owner.take_result(e.listener,e.job,r);
 a.post_stop=f.owner.snapshot().stop_at;
 if(ready){a.accepted=r.accepted_at;result(r);}
 else std::cout<<"{\"ready\":false,\"job\":\""<<e.job<<"\"}"<<std::endl;
}

int main(int argc,char** argv){
 if(argc!=2)return 2;
 const auto axis=static_cast<unsigned>(std::stoul(argv[1]));if(axis<1||axis>2)return 2;
 const HANDLE timer=CreateWaitableTimerExW(nullptr,nullptr,CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,TIMER_ALL_ACCESS);
 if(!timer){std::cerr<<"high resolution timer create failed "<<GetLastError()<<std::endl;return 6;}
 Bench f(axis);Audit a;Time job=0;std::mutex lock;std::deque<Input> queue;bool done=false;
 const auto origin=Clock::now();
 const auto elapsed=[&](){return static_cast<Time>(std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now()-origin).count());};
 std::thread reader([&](){std::string line;while(std::getline(std::cin,line)){
  const auto at=elapsed();std::lock_guard<std::mutex> guard(lock);queue.push_back({line,at});
 }std::lock_guard<std::mutex> guard(lock);done=true;});
 for(;;){
  Input input;bool available=false,finished=false;
  {std::lock_guard<std::mutex> guard(lock);if(!queue.empty()){input=queue.front();queue.pop_front();available=true;}finished=done&&queue.empty();}
  f.p.now=elapsed();if(f.p.now-a.previous>a.gap)a.gap=f.p.now-a.previous;a.previous=f.p.now;++a.ticks;
  f.owner.tick(); // One poll at actual current time; no missed-ms backfill.
  if(available)handle(f,input,job,a);
  if(finished)break;
  LARGE_INTEGER due;due.QuadPart=-10000; // Relative 1ms, 100ns units.
  if(!SetWaitableTimer(timer,&due,0,nullptr,nullptr,FALSE)||WaitForSingleObject(timer,2000)!=WAIT_OBJECT_0){
   std::cerr<<"high resolution timer wait failed "<<GetLastError()<<std::endl;std::quick_exit(7);
  }
 }
 reader.join();CloseHandle(timer);return 0;
}
