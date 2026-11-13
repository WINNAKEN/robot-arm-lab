#pragma once
#include "robot_core/mks_codec.hpp"
namespace robot_config {
constexpr std::array<std::uint8_t,7> settings{0x82,0x84,0x8A,0x8B,0x8C,0x4A,0x98};
struct ConfigSample {bool valid{false};std::uint32_t value{0};std::uint64_t tx_at{0},dequeued_at{0};};
// Same pure predicates used by the actor at every admission/deadline check.
bool sample_fresh(const ConfigSample& sample,std::uint64_t now) noexcept;
bool sample_headroom(const ConfigSample& sample,std::uint64_t now,std::uint64_t margin) noexcept;
using ConfigSamples=std::array<std::array<ConfigSample,7>,2>;
enum class DecodeError : std::uint8_t {None,Frame,Unsupported,Value};
struct ConfigValue {DecodeError error{DecodeError::Frame};std::uint32_t value{0};};
robot_core::mks::EncodeResult read_config(std::uint16_t axis,std::uint8_t setting) noexcept;
robot_core::mks::EncodeResult heartbeat1000(std::uint16_t axis) noexcept;
ConfigValue parse_config(const robot_core::mks::Frame& frame,std::uint8_t expected) noexcept;
bool parse_heartbeat_ack(const robot_core::mks::Frame& frame) noexcept;
} // namespace robot_config
