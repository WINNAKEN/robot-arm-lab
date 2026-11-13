#pragma once
#include "protocol.hpp"
#include <array>
namespace reader144 {
struct Frame {uint16_t id=0; uint8_t dlc=0; bool ext=false,rtr=false; std::array<uint8_t,8> data{};};
enum class Rx { Frame, Timeout, Error };
enum class Status { Ok, Denied, Latched, Install, Start, Transmit, Timeout, Receive, Flood, Cleanup };
struct Result {Status status=Status::Denied; Frame frame{}; uint32_t rejected=0;};
inline const char* name(Status s) {
    constexpr const char* names[]={"OK","DENIED","LATCHED","INSTALL_ERROR","START_ERROR","TX_ERROR","TIMEOUT","RX_ERROR","RX_LIMIT","CLEANUP_ERROR"};
    return names[static_cast<unsigned>(s)];
}
inline bool valid(const Request& q) {
    return q.kind==Kind::Read&&q.id>=1&&q.id<=16&&
        (q.rate==125000||q.rate==250000||q.rate==500000||q.rate==1000000)&&
        (q.op==0x31||q.op==0x32||q.op==0xF1||q.op==0x3A);
}
inline bool reply(const Request& q,const Frame& f) {
    const uint8_t wanted=q.op==0x31?8:(q.op==0x32?4:3);
    if(f.ext||f.rtr||f.id!=q.id||f.dlc!=wanted||f.data[0]!=q.op) return false;
    unsigned sum=q.id;
    for(unsigned i=0;i+1<f.dlc;++i) sum+=f.data[i];
    return static_cast<uint8_t>(sum)==f.data[f.dlc-1];
}
// Backend bounds: TX <=25ms, RX waits <=20ms, session receive <=250ms.
// Install/start/stop/uninstall are synchronous SDK state transitions.
template<class Backend> Result run(Backend& b,const Request& q,bool& latched,uint32_t& total_tx) {
    Result r;
    if(!valid(q)) return r;
    if(latched) {r.status=Status::Latched;return r;}
    if(!b.install(q.rate)) {latched=true;r.status=Status::Install;return r;}
    const bool started=b.start();
    r.status=Status::Start;
    if(started) {
        Frame tx;tx.id=q.id;tx.dlc=2;tx.data[0]=q.op;tx.data[1]=static_cast<uint8_t>(q.id+q.op);
        ++total_tx;
        if(!b.transmit(tx,true,25)) r.status=Status::Transmit;
        else {
            r.status=Status::Timeout;
            const uint64_t begin=b.now_ms();
            for(unsigned count=0;count<32;++count) {
                const uint64_t now=b.now_ms();
                if(now<begin||now-begin>=250) break;
                Frame f;
                const uint32_t remaining=static_cast<uint32_t>(250-(now-begin));
                const Rx rx=b.receive(f,remaining<20?remaining:20);
                if(rx==Rx::Error) {r.status=Status::Receive;break;}
                if(rx==Rx::Frame) {
                    if(reply(q,f)) {r.status=Status::Ok;r.frame=f;break;}
                    ++r.rejected;
                }
                if(count==31) r.status=Status::Flood;
            }
        }
    }
    const bool stopped=!started||b.stop();
    const bool removed=b.uninstall();
    if(!stopped||!removed) {latched=true;r.status=Status::Cleanup;}
    return r;
}
}
