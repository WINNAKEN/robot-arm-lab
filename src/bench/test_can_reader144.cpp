#include "../firmware/can_reader144/main/flow.hpp"
#include <cstdlib>
#include <iostream>
#include <vector>
using namespace reader144;
int checks=0;
#define CHECK(x) do {++checks;if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<" : "<<#x<<"\n";std::exit(1);}}while(0)
struct Fake {
    bool install_ok=true,start_ok=true,tx_ok=true,stop_ok=true,remove_ok=true,single=false;
    int installs=0,starts=0,txs=0,rxs=0,stops=0,removes=0;
    uint64_t now=0;Rx rx=Rx::Timeout;Frame request{},response{};
    bool install(uint32_t){++installs;return install_ok;}
    bool start(){++starts;return start_ok;}
    bool transmit(Frame f,bool s,uint32_t ms){++txs;request=f;single=s;CHECK(ms<=25);return tx_ok;}
    Rx receive(Frame& f,uint32_t ms){++rxs;CHECK(ms<=20);now+=rx==Rx::Timeout?ms:1;f=response;return rx;}
    uint64_t now_ms(){return now;}
    bool stop(){++stops;return stop_ok;}
    bool uninstall(){++removes;return remove_ok;}
};
int main(){
    CHECK(parse("INFO").kind==Kind::Info);
    for(auto id:{"1","16"}) for(auto rate:{"125000","250000","500000","1000000"})
      for(auto op:{"31","32","F1","3A"}) CHECK(parse(std::string("READ ")+id+" "+rate+" "+op).kind==Kind::Read);
    for(auto s:{"READ 0 500000 31","READ 17 500000 31","READ 1 500001 31","READ 42949672960 500000 31","READ 1 500000 F3","READ 1 500000 FD","READ 1 500000 F6","READ 1 500000 FF","READ 1 500000 80","RAW 1 F3 01","READ 1 500000 31 EXTRA","INFO EXTRA","READ 1x 500000 31","READ -1 500000 31","READ 1 500000 0x31","READ\t1 500000 31"})
      CHECK(parse(s).kind==Kind::Denied);
    const char binary[]={'I','N','F','O',0,'x'};CHECK(parse({binary,sizeof(binary)}).kind==Kind::Denied);
    Lines l;for(int i=0;i<81;++i) CHECK(l.push('A')==Lines::None);
    CHECK(l.push('\n')==Lines::Rejected);
    for(char c:std::string("INFO\r\n")){const auto e=l.push(c);if(c=='\n'){CHECK(e==Lines::Line);CHECK(parse(l.line()).kind==Kind::Info);}}
    CHECK(l.push(0)==Lines::None);CHECK(l.push('\n')==Lines::Rejected);
    auto q=parse("READ 1 500000 3A");
    for(const auto op:{0x31,0x32,0xF1,0x3A}) {
      Fake f;bool latch=false;uint32_t tx=0;auto request=q;request.op=static_cast<uint8_t>(op);
      f.rx=Rx::Frame;f.response.id=1;f.response.dlc=op==0x31?8:(op==0x32?4:3);f.response.data[0]=static_cast<uint8_t>(op);
      f.response.data[f.response.dlc-1]=static_cast<uint8_t>(1+op);
      CHECK(run(f,request,latch,tx).status==Status::Ok);CHECK(f.txs==1);CHECK(f.single);CHECK(f.removes==1);CHECK(!latch);
      ++f.response.data[f.response.dlc-1];CHECK(!reply(request,f.response));
      --f.response.data[f.response.dlc-1];++f.response.dlc;CHECK(!reply(request,f.response));
    }
    for(int mode=0;mode<8;++mode){
      Fake f;bool latch=false;uint32_t tx=0;
      if(mode==0){f.rx=Rx::Frame;f.response.id=1;f.response.dlc=3;f.response.data={0x3A,0,0x3B};}
      if(mode==2)f.install_ok=false;
      if(mode==3)f.start_ok=false;
      if(mode==4)f.tx_ok=false;
      if(mode==5)f.rx=Rx::Error;
      if(mode==6){f.rx=Rx::Frame;f.response.id=2;}
      if(mode==7)f.stop_ok=false;
      const auto r=run(f,q,latch,tx);
      const Status expected[]={Status::Ok,Status::Timeout,Status::Install,Status::Start,Status::Transmit,Status::Receive,Status::Flood,Status::Cleanup};
      CHECK(r.status==expected[mode]);CHECK(f.txs<=1);
      if(f.txs){CHECK(f.single);CHECK(f.request.id==1);CHECK(f.request.dlc==2);CHECK(f.request.data[0]==0x3A);CHECK(f.request.data[1]==0x3B);}
      if(mode!=2)CHECK(f.removes==1);
      if(mode==1)CHECK(f.now<=250);
      if(mode==6)CHECK(f.rxs==32);
      if(latch){const int before=f.installs;CHECK(run(f,q,latch,tx).status==Status::Latched);CHECK(f.installs==before);}
    }
    {Fake f;f.remove_ok=false;bool latch=false;uint32_t tx=0;CHECK(run(f,q,latch,tx).status==Status::Cleanup);CHECK(latch);CHECK(run(f,q,latch,tx).status==Status::Latched);CHECK(f.txs==1);}
    {Fake f;bool latch=false;uint32_t tx=0;auto bad=q;bad.op=0xF3;CHECK(run(f,bad,latch,tx).status==Status::Denied);CHECK(f.installs==0);CHECK(tx==0);}
    Frame frame;frame.id=1;frame.dlc=3;frame.data={0x3A,0,0x3B};CHECK(reply(q,frame));
    frame.data[2]=0;CHECK(!reply(q,frame));frame.data[2]=0x3B;frame.ext=true;CHECK(!reply(q,frame));frame.ext=false;frame.rtr=true;CHECK(!reply(q,frame));
    std::cout<<"PASS "<<checks<<" checks\n";
}
