#pragma once
#include "robot_gate/control_gate.hpp"
#include "robot_config/codec.hpp"
#include "robot_can/stop_link.hpp"
#include "robot_run/joint_angles.hpp"
namespace robot_boot { class Supervisor; }
namespace robot_run {
using Time=std::uint64_t;
enum class State : std::uint8_t { Idle, Checking, Ready, AwaitStart, Moving, Completing, Stopping, StoppedRecheck, Fault };
enum class Fault : std::uint8_t { None, Profile, Clock, Service, Overflow, Port, Bus, Rx, Tx, Deadline, Observation, Command, Gate, StopTiming, Cleanup, ConfigMismatch };
enum class EnablePolicy : std::uint8_t { LegacyAllEnabled, SingleSelected };
struct Profile {
    robot_gate::Config gate{};
    EnablePolicy enable_policy{EnablePolicy::LegacyAllEnabled}; std::uint16_t selected_axis{0};
    robot_core::StopProfile stop{};
    bool normal_approved{false}, post_maintenance_enable_seed_approved{false};
    std::uint64_t counts_per_100pulse{0}; std::int8_t dir0_sign{0};
};
class BootEvidence {
    friend class robot_boot::Supervisor; friend class BenchRun;
public:
    BootEvidence() noexcept = default;
    BootEvidence(const BootEvidence&)=delete; BootEvidence& operator=(const BootEvidence&)=delete;
    BootEvidence(BootEvidence&& other) noexcept { *this=static_cast<BootEvidence&&>(other); }
    BootEvidence& operator=(BootEvidence&& other) noexcept { if(this!=&other){profile_=other.profile_;settings_=other.settings_;principal_=other.principal_;admit_=other.admit_;config_=other.config_;authority_=other.authority_;valid_=other.valid_;port_=other.port_;other.valid_=false;other.port_=nullptr;} return *this; }
    bool valid() const noexcept { return valid_; }
private: robot_config::ConfigSamples settings_{}; const robot_can::CanPort* port_{nullptr}; Profile profile_{}; Time principal_{0},admit_{0},config_{0},authority_{0}; bool valid_{false};
};
struct Status {
    State state{State::Idle}; Fault fault{Fault::None}; Time fault_at{0}, stop_at{0}, preparation_at{0};
    bool stop_verified{false}, torque_unknown{false}, manual_power_cut_required{false}; robot_can::CloseResult closed{};
};
class BenchRun {
public:
    BenchRun(robot_can::CanPort& port,const Profile& profile) noexcept;
    BenchRun(robot_can::CanPort& port,const Profile& profile,
             const std::array<robot_joint::Calibration,2>& calibration) noexcept
        : port_(port),profile_(profile),gate_(profile.gate),stop_(port),joint_calibration_(calibration) {
        snapshot_.profile=profile.gate.profile; snapshot_.count=profile.gate.count; snapshot_.revision=1;
        for(unsigned i=0;i<2;++i) snapshot_.axes[i].id=profile.gate.axes[i];
    }
    BenchRun(const BenchRun&)=delete; BenchRun& operator=(const BenchRun&)=delete;
    void begin() noexcept;
    void begin_from_boot(BootEvidence&& evidence) noexcept;
    void poll() noexcept;
    robot_gate::Id open_session() noexcept;
    robot_gate::Id open_session(Time authenticated_principal) noexcept;
    void close_session(robot_gate::Id session) noexcept;
    robot_gate::Result request(const robot_gate::Request& request) noexcept;
    robot_gate::Result request_joint_step(const robot_gate::Request& r,unsigned joint,robot_joint::Step step) noexcept {
        // The Stop path must never depend on coordinates or physical calibration.
        if(r.op==robot_gate::Op::Stop) return request(r);
        if(r.op!=robot_gate::Op::Move) return {robot_gate::Error::BadRequest,0,0};
        if(joint_mapping_revoked_ || !profile_.normal_approved || profile_.gate.count<1 || profile_.gate.count>2)
            return {robot_gate::Error::Denied,0,0};
        for(unsigned i=0;i<profile_.gate.count;++i) if(profile_.gate.axes[i]==r.axis){
            const auto& cal=joint_calibration_[i];
            if(cal.boot!=profile_.gate.boot || cal.profile!=profile_.gate.profile || cal.axis!=r.axis)
                return {robot_gate::Error::Denied,0,0};
            const auto prepared=robot_joint::prepare(cal,joint,step);
            if(!prepared.ok) return {robot_gate::Error::BadRequest,0,0};
            auto mapped=r; mapped.direction=prepared.direction;
            return request(mapped);
        }
        return {robot_gate::Error::AxisDenied,0,0};
    }
    // No replacement/reactivation API: use a fresh boot/profile/actor lifetime.
    void revoke_joint_mapping() noexcept {
        joint_mapping_revoked_=true;
        if(begun_ && active()) enter_stop(Fault::Profile);
    }
    struct JointStepInfo {bool available{false};std::uint16_t joint{0};};
    JointStepInfo joint_step_info(std::uint16_t axis)const noexcept {
        if(joint_mapping_revoked_ || !begun_ || !active() || !profile_.normal_approved || profile_.gate.count<1 || profile_.gate.count>2)return {};
        for(unsigned i=0;i<profile_.gate.count;++i)if(profile_.gate.axes[i]==axis){
            const auto& c=joint_calibration_[i];
            if(c.boot!=profile_.gate.boot || c.profile!=profile_.gate.profile || c.axis!=axis)return {};
            const double degrees=36000./(static_cast<double>(c.fullsteps)*c.microsteps*c.reduction);
            if(!robot_joint::prepare(c,c.joint,{robot_joint::StepUnit::CadDegrees,degrees}).ok)return {};
            return {true,c.joint};
        }
        return {};
    }
    Status status() const noexcept {return status_;}
    // Current proof, not a promise inferred from a previous UI snapshot.
    bool acquisition_ready() const noexcept {
        return active() && status_.state==State::Ready && snapshot_.ready && proof();
    }
    robot_gate::Status gate_status() const noexcept {return gate_.status();}
    const robot_gate::Snapshot& snapshot() const noexcept {return snapshot_;}
    const robot_can::StopLink& stop_link() const noexcept {return stop_;}
    std::size_t raw_count() const noexcept {return raw_size_;}
    std::uint64_t raw_dropped() const noexcept {return raw_dropped_;}
 bool position_sample(unsigned axis,std::int64_t& value,Time& tx_at,Time& at)const noexcept;
 Time oldest_configuration_at()const noexcept;
    bool configuration_sample(unsigned axis,unsigned setting,robot_config::ConfigSample& output) const noexcept;
    std::uint64_t configuration_refresh_count() const noexcept {return config_refreshes_;}
private:
    struct Sample {bool valid{false}; std::int64_t value{0}; Time tx{0}, at{0};};
    struct Proof {std::array<Sample,4> sample{}; std::array<Sample,3> positions{}; unsigned positions_count{0};};
    struct Pending {bool active{false}, confirmed{false}; unsigned axis{0}, code{0}; Time tx{0}, deadline{0};bool configuration{false};};
    std::uint32_t expected_configuration(unsigned axis,unsigned setting) const noexcept;
    bool configurations_fresh(Time now) const noexcept;
    bool configuration_headroom(Time now,Time margin) const noexcept;
    bool expected_enabled(unsigned axis) const noexcept;
    bool active() const noexcept;
    bool time_ok() noexcept;
    bool deadlines() noexcept;
    bool health(bool empty=false) noexcept;
    bool submit(const robot_core::mks::Frame& frame,Time before,unsigned axis,unsigned code,bool move,bool configuration=false) noexcept;
    void receive(const robot_can::RxFrame& rx) noexcept;
    void schedule() noexcept;
    bool fresh(unsigned axis,unsigned code,Time after=0) const noexcept;
    bool proof(bool after_completion=false) const noexcept;
    void publish(bool ready) noexcept;
    void sync_gate() noexcept;
    void enter_stop(Fault fault=Fault::None) noexcept;
    void stop_poll(bool begin) noexcept;
    void emergency(Fault fault) noexcept;
    bool add(Time base,Time delta,Time& out) noexcept;
    void record(const robot_can::RxFrame& rx) noexcept;
    static int code_index(std::uint8_t code) noexcept;
    robot_can::CanPort& port_; Profile profile_; robot_gate::ControlGate gate_; robot_can::StopLink stop_;
    const std::array<robot_joint::Calibration,2> joint_calibration_{};
    bool joint_mapping_revoked_{false};
    bool boot_approved_{false}; Time authority_until_{0},principal_{0};
    robot_config::ConfigSamples configurations_{};std::array<std::array<Time,7>,2> last_config_{};Time config_refreshes_{0};bool config_slot_{false},premise_invalidated_{false};
    struct PrincipalSession {Time session{0},principal{0};}; std::array<PrincipalSession,2> principal_sessions_{};
    Status status_{}; robot_gate::Snapshot snapshot_{};
    std::array<Proof,2> proofs_{}; std::array<std::array<Time,4>,2> last_read_{};
    Pending read_{}; robot_gate::Intent move_{};
    std::array<robot_can::RxFrame,32> raw_{}; std::size_t raw_size_{0},raw_head_{0}; Time raw_dropped_{0};
    Time last_clock_{0},last_poll_{0},operation_at_{0},checking_until_{0},next_read_{0};
    Time tx_deadline_{0},move_until_{0},start_until_{0},completed_at_{0},stop_until_{0},isolation_until_{0},prep_until_{0};
    std::int64_t baseline_{0}; unsigned cursor_{0}; bool inflight_{false},tx_move_{false},started_{false},completed_{false};
    bool begun_{false},touched_{false},ever_ready_{false},saw_clock_{false},preparation_seen_{false};
};
} // namespace robot_run
