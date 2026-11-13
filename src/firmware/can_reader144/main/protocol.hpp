#pragma once
#include <array>
#include <cstddef>
#include <cstdint>
#include <string_view>
namespace reader144 {
enum class Kind { Denied, Info, Read };
struct Request { Kind kind=Kind::Denied; uint16_t id=0; uint32_t rate=0; uint8_t op=0; };
inline bool decimal(std::string_view s,uint32_t& value) {
    if(s.empty()) return false;
    value=0;
    for(char c:s) {
        if(c<'0'||c>'9'||value>(UINT32_MAX-static_cast<unsigned>(c-'0'))/10) return false;
        value=value*10+static_cast<unsigned>(c-'0');
    }
    return true;
}
inline Request parse(std::string_view s) {
    std::array<std::string_view,4> t{}; size_t n=0,pos=0;
    for(unsigned char c:s) if(c<32||c>126) return {};
    while(pos<s.size()) {
        while(pos<s.size()&&s[pos]==' ') ++pos;
        if(pos==s.size()) break;
        const size_t start=pos;
        while(pos<s.size()&&s[pos]!=' ') ++pos;
        if(n==t.size()) return {};
        t[n++]=s.substr(start,pos-start);
    }
    if(n==1&&t[0]=="INFO") return {Kind::Info,0,0,0};
    uint32_t id=0,rate=0; uint8_t op=0;
    if(n!=4||t[0]!="READ"||!decimal(t[1],id)||id<1||id>16||!decimal(t[2],rate)) return {};
    if(rate!=125000&&rate!=250000&&rate!=500000&&rate!=1000000) return {};
    if(t[3]=="31") op=0x31;
    else if(t[3]=="32") op=0x32;
    else if(t[3]=="F1") op=0xF1;
    else if(t[3]=="3A") op=0x3A;
    else return {};
    return {Kind::Read,static_cast<uint16_t>(id),rate,op};
}
class Lines {
    std::array<char,80> b_{}; size_t n_=0,done_=0; bool bad_=false;
public:
    enum Event { None, Line, Rejected };
    Event push(unsigned char c) {
        if(c=='\n') {
            done_=n_;
            if(done_&&b_[done_-1]=='\r') --done_;
            const bool bad=bad_; n_=0; bad_=false;
            if(bad) {done_=0;return Rejected;}
            return Line;
        }
        if(bad_) return None;
        if(n_==b_.size()||c==0||c>126||(c<32&&c!='\r')) {bad_=true;return None;}
        b_[n_++]=static_cast<char>(c); return None;
    }
    std::string_view line() const { return {b_.data(),done_}; }
};
}
