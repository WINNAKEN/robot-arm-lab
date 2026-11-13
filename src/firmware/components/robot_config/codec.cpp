#include "robot_config/codec.hpp"
#include <limits>
namespace robot_config {
bool sample_fresh(const ConfigSample& sample,std::uint64_t now) noexcept {
 constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();
 return sample.valid && sample.tx_at<=sample.dequeued_at && sample.dequeued_at<=now && sample.dequeued_at<=maximum-4000 && now<sample.dequeued_at+4000;
}
bool sample_headroom(const ConfigSample& sample,std::uint64_t now,std::uint64_t margin) noexcept {
 constexpr auto maximum=std::numeric_limits<std::uint64_t>::max();
 return sample_fresh(sample,now) && now<=maximum-margin && sample.dequeued_at+4000>now+margin;
}
namespace {unsigned width(std::uint8_t c)noexcept{switch(c){case 0x82:case 0x84:case 0x8A:case 0x4A:return 1;case 0x8B:case 0x8C:return 2;case 0x98:return 4;default:return 0;}}
bool valid(const robot_core::mks::Frame& f)noexcept{if(f.id<1||f.id>2||f.extended||f.rtr||f.dlc<2||f.dlc>8)return false;unsigned sum=f.id;for(unsigned i=0;i<f.dlc-1;++i)sum+=f.data[i];return static_cast<std::uint8_t>(sum)==f.data[f.dlc-1];}
void checksum(robot_core::mks::Frame& f)noexcept{unsigned sum=f.id;for(unsigned i=0;i<f.dlc-1;++i)sum+=f.data[i];f.data[f.dlc-1]=static_cast<std::uint8_t>(sum);}}
robot_core::mks::EncodeResult read_config(std::uint16_t axis,std::uint8_t c)noexcept{if(axis<1||axis>2||width(c)==0)return{robot_core::mks::Error::InvalidValue,{}};robot_core::mks::Frame f;f.id=axis;f.dlc=3;f.data[0]=0;f.data[1]=c;checksum(f);return{robot_core::mks::Error::None,f};}
robot_core::mks::EncodeResult heartbeat1000(std::uint16_t axis)noexcept{if(axis<1||axis>2)return{robot_core::mks::Error::InvalidAxis,{}};robot_core::mks::Frame f;f.id=axis;f.dlc=6;f.data={0x98,0,0,3,0xE8,0,0,0};checksum(f);return{robot_core::mks::Error::None,f};}
ConfigValue parse_config(const robot_core::mks::Frame& f,std::uint8_t c)noexcept{if(!valid(f)||f.data[0]!=c||width(c)==0)return{};if(f.dlc==4&&f.data[1]==0xFF&&f.data[2]==0xFF)return{DecodeError::Unsupported,0};if(f.dlc!=width(c)+2)return{};std::uint32_t v=0;for(unsigned i=1;i<f.dlc-1;++i)v=(v<<8)|f.data[i];return{DecodeError::None,v};}
bool parse_heartbeat_ack(const robot_core::mks::Frame& f)noexcept{return valid(f)&&f.dlc==3&&f.data[0]==0x98&&f.data[1]==1;}
} // namespace robot_config
