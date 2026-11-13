#pragma once
#include "robot_config/codec.hpp"
namespace robot_boot {
using robot_config::settings; using robot_config::DecodeError; using robot_config::ConfigValue;
using robot_config::read_config; using robot_config::heartbeat1000;
using robot_config::parse_config; using robot_config::parse_heartbeat_ack;
} // namespace robot_boot
