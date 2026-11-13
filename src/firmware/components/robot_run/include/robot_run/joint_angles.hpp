#pragma once
#include <array>
#include <cmath>
#include <cstdint>

namespace robot_joint {
// Fixed source: v2 c784ee45...f84bc1 / kinematics fe000e47...ae50,
// approved021 core 1eb5d41f...b4d46 and finite native025 direction observation.
constexpr double pi = 3.141592653589793238462643383279502884;
constexpr std::array<double,6> pose_deg{{15.,-50.,70.,15.,25.,-10.}};
enum class Space : std::uint8_t { CadDegrees, CoreDeltaRadians, CoreGeometricRadians };
enum class StepUnit : std::uint8_t { CadDegrees, CoreRadians };
enum class Layout : std::uint8_t { Unknown, FixedV2_025 };
struct Coordinate { Space space{Space::CadDegrees}; double value{0}; };
struct Step { StepUnit unit{StepUnit::CadDegrees}; double value{0}; };
struct Converted { bool ok{false}; double cad_deg{0}, delta_rad{0}, geometric_rad{0}; };
inline Converted convert(unsigned joint, Coordinate input) noexcept {
    if(joint<1 || joint>6 || !std::isfinite(input.value)) return {};
    const double offset=pose_deg[joint-1]*pi/180.;
    double delta=0;
    switch(input.space){
    case Space::CadDegrees: delta=input.value*(pi/180.);break;
    case Space::CoreDeltaRadians: delta=input.value;break;
    case Space::CoreGeometricRadians: delta=input.value-offset;break;
    default:return {};
    }
    const double cad=delta*(180./pi), geometric=delta+offset;
    if(!std::isfinite(delta) || !std::isfinite(cad) || !std::isfinite(geometric)) return {};
    return {true,cad,delta,geometric};
}
// Trusted setup only, copied into an actor at construction, never web payload.
// Encoder-count direction in robot_run::Profile is a different calibration.
struct Calibration {
    bool measured{false}; Layout layout{Layout::Unknown};
    std::uint64_t boot{0},profile{0}; std::uint16_t axis{0},joint{0};
    std::uint16_t fullsteps{0},microsteps{0};
    double reduction{0}; std::int8_t dir0_joint_sign{0};
};
struct Prepared { bool ok{false}; std::uint8_t direction{0}; double delta_rad{0}; };
inline Prepared prepare(const Calibration& cal, unsigned joint, Step input) noexcept {
    if(!cal.measured || cal.layout!=Layout::FixedV2_025 || cal.joint!=joint || joint<1 || joint>6 ||
       (cal.axis!=1 && cal.axis!=2) || cal.boot==0 || cal.profile==0 ||
       (cal.fullsteps!=200 && cal.fullsteps!=400) || cal.microsteps!=16 ||
       !std::isfinite(cal.reduction) || cal.reduction<=0 ||
       (cal.dir0_joint_sign!=1 && cal.dir0_joint_sign!=-1) || !std::isfinite(input.value)) return {};
    double delta=0;
    switch(input.unit){
    case StepUnit::CadDegrees: delta=input.value*(pi/180.);break;
    case StepUnit::CoreRadians: delta=input.value;break;
    default:return {};
    }
    if(!std::isfinite(delta) || delta==0) return {};
    const double pulses=std::fabs(delta)*cal.fullsteps*cal.microsteps*cal.reduction/(2*pi);
    if(!std::isfinite(pulses) || std::fabs(pulses-100.)>1e-9) return {};
    const bool dir0=(delta>0)==(cal.dir0_joint_sign>0);
    return {true,static_cast<std::uint8_t>(dir0?0:1),delta};
}
} // namespace robot_joint
