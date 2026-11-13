#include "robot_phone/wire.hpp"
#include <limits>
#include <cmath>
namespace robot_phone {
namespace {
bool number(std::string_view s,Time& n)noexcept{if(s.empty())return false;
n=0;
for(char c:s){if(c<'0'||c>'9')return false;
const auto d=static_cast<Time>(c-'0');
if(n>(std::numeric_limits<Time>::max()-d)/10)return false;
n=n*10+d;
}
return true;
}
bool iequal(std::string_view a,std::string_view b)noexcept{if(a.size()!=b.size())return false;
for(std::size_t i=0;i<a.size();++i){char c=a[i],d=b[i];
if(c>='A'&&c<='Z')c=static_cast<char>(c+32);
if(d>='A'&&d<='Z')d=static_cast<char>(d+32);
if(c!=d)return false;
}
return true;
}
bool token(char c)noexcept{return(c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_';
}
bool decimal(std::string_view text,double& out)noexcept{
 const bool negative=!text.empty()&&text.front()=='-';if(negative)text.remove_prefix(1);
 const auto dot=text.find('.');const auto whole=text.substr(0,dot);
 if(whole.empty()||whole.size()>6||(whole.size()>1&&whole.front()=='0'))return false;
 Time integer=0,fraction=0;if(!number(whole,integer))return false;
 double value=static_cast<double>(integer);
 if(dot!=std::string_view::npos){const auto tail=text.substr(dot+1);
  if(tail.empty()||tail.size()>18||!number(tail,fraction))return false;
  double scale=1;for(std::size_t i=0;i<tail.size();++i)scale*=10;
  value+=static_cast<double>(fraction)/scale;
 }
 if(!std::isfinite(value)||value==0)return false;
 out=negative?-value:value;return true;
}
}
bool parse(std::string_view body,Wire& out)noexcept{
 if(body.empty()||body.size()>256)return false;
 for(char c:body)if(c<33||c>126)return false;
 std::array<std::string_view,12> f{};
 std::size_t start=0,index=0;
 for(std::size_t i=0;i<=body.size();++i)if(i==body.size()||body[i]=='|'){if(index==f.size())return false;
 f[index++]=body.substr(start,i-start);
 start=i+1;
 }
 if(!((index==11&&f[0]=="v1")||(index==12&&f[0]=="v2")))return false;
 Wire w;
 Time axis=0,direction=0,unloaded=0;
 if(!number(f[1],w.boot)||!number(f[2],w.phase)||!number(f[3],w.seq)||!number(f[4],w.request)||!number(f[6],w.lease)||!number(f[7],w.ticket)||!number(f[8],axis)||axis>2)return false;
 if(f[0]=="v2"){
  Time joint=0;if(f[5]!="joint-step"||axis==0||!number(f[9],joint)||joint<1||joint>6||(f[10]!="deg"&&f[10]!="rad"))return false;
  if(!decimal(f[11],w.angle))return false;
  w.op=Op::JointStep;w.axis=static_cast<std::uint16_t>(axis);w.joint=static_cast<std::uint16_t>(joint);w.radians=f[10]=="rad";out=w;return true;
 }
 if(!number(f[9],direction)||!number(f[10],unloaded)||direction>1||f[9].size()!=1||unloaded>1||f[10].size()!=1)return false;
 constexpr std::array<std::string_view,15> names{{"maintenance","maintenance-renew","unloaded","disable-all","finish-maintenance","drive","enable-selected","handoff","acquire","renew","arm","ticket","move","release","stop"}
 };
 bool found=false;
 for(std::size_t i=0;i<names.size();++i)if(f[5]==names[i]){w.op=static_cast<Op>(i);
 found=true;
 }
 // JointStep already occupies15; preserve all historical enum values.
 if(!found&&f[5]=="handoff-acquire"){w.op=Op::HandoffAcquire;found=true;}
 if(!found&&f[5]=="handoff-result"){w.op=Op::HandoffResult;found=true;}
 if(!found)return false;
 if((w.op==Op::HandoffAcquire||w.op==Op::HandoffResult)&&
    (axis==0||direction!=0||unloaded!=0))return false;
 w.axis=static_cast<std::uint16_t>(axis);
 w.direction=static_cast<std::uint8_t>(direction);
 w.unloaded=unloaded==1;
 out=w;
 return true;
}
bool equal_secret(std::string_view a,std::string_view b)noexcept{if(a.size()!=32||b.size()!=32)return false;
unsigned diff=0;
for(std::size_t i=0;i<32;++i)diff|=static_cast<unsigned char>(a[i])^static_cast<unsigned char>(b[i]);
return diff==0;
}
Error origin_host(Listener l,std::string_view host,std::string_view origin)noexcept{if(host!=(l==Listener::Normal?"192.168.4.1":"192.168.4.1:8081"))return Error::Host;
if(origin!="http://192.168.4.1")return Error::Origin;
return Error::None;
}
bool HeaderGuard::feed(const char* bytes,std::size_t size)noexcept{
 if(failed_)return false;
 if(complete_)return true;
 for(std::size_t i=0;i<size;++i){if(used_==raw_.size()||bytes[i]=='\0'){failed_=true;
 return false;
 }
 raw_[used_++]=bytes[i];
 if(used_>=4&&std::string_view(raw_.data()+used_-4,4)=="\r\n\r\n"){complete_=validate();
 failed_=!complete_;
 return complete_;
 }
 }
 return true;
}
bool HeaderGuard::validate()noexcept{
 std::string_view raw(raw_.data(),used_);
 auto line_end=raw.find("\r\n");
 if(line_end==std::string_view::npos)return false;
 auto request=raw.substr(0,line_end);
 auto space=request.find(' ');
 if(space==std::string_view::npos||space==0)return false;
 for(char c:request.substr(0,space))if(c<'A'||c>'Z')return false;
 auto rest=request.substr(space+1);
 auto second=rest.find(' ');
 if(second==std::string_view::npos||second==0||rest.substr(second+1)!="HTTP/1.1")return false;
 for(char c:rest.substr(0,second))if(c<=32||c>=127)return false;
 constexpr std::array<std::string_view,7> unique{{"host","origin","authorization","x-session-credential","x-pairing-credential","content-length","content-type"}
 };
 std::array<bool,7> seen{};
 std::size_t at=line_end+2;
 while(at<raw.size()){line_end=raw.find("\r\n",at);
 if(line_end==std::string_view::npos)return false;
 auto line=raw.substr(at,line_end-at);
 at=line_end+2;
 if(line.empty())return at==raw.size()&&seen[0];
 auto colon=line.find(':');
 if(colon==std::string_view::npos||colon==0)return false;
 auto name=line.substr(0,colon);
 for(char c:name)if(!token(c))return false;
 auto value=line.substr(colon+1);
 if(value.empty())return false;
 for(char c:value)if(c<32||c>=127)return false;
 if(iequal(name,"transfer-encoding"))return false;
 for(std::size_t i=0;i<unique.size();++i)if(iequal(name,unique[i])){if(seen[i])return false;
 seen[i]=true;
 if(i==5){if(value.front()==' ')value.remove_prefix(1);
 Time length=0;
 if(!number(value,length)||length>256)return false;
 }
 }
 }
 return false;
}
} // namespace robot_phone
