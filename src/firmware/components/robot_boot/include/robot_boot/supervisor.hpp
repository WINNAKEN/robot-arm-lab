#pragma once
#include "robot_run/bench_run.hpp"
#include "robot_boot/config_codec.hpp"
namespace robot_boot {
using Time=std::uint64_t;
enum class State:std::uint8_t {Idle,ReadConfig,Observe,NeedsMaintenance,ReadyDisabled,Disabling,Heartbeat,Enabling,Granted,HandedOff,Stopping,StoppedRecheck,Fault};
enum class Error:std::uint8_t {None,Profile,Auth,Replay,Lease,Denied,Busy,Clock,Time,Port,Config,Proof,Protocol,Exhausted,Cleanup};
enum class Op:std::uint8_t {AcquireMaintenance,RenewMaintenance,ConfirmUnloaded,DisableAll,FinishMaintenance,AcquireDrive,EnableSelected,Stop};
struct Request{Time boot{0},session{0},seq{0},request{0},lease{0};Op op{Op::AcquireMaintenance};std::uint16_t axis{0};bool unloaded_confirmed{false};};
struct Result{Error error{Error::None};Time lease{0};};
struct Profile{robot_run::Profile run{};bool hardware_identity_approved{false};};
struct Status{State state{State::Idle};Error error{Error::None};Time fault_at{0},stop_at{0},lease_until{0},owner{0};bool heartbeat_verified{false},stop_verified{false},torque_unknown{true},manual_power_cut_required{false};robot_can::CloseResult closed{};};
class Supervisor {
public:
 Supervisor(robot_can::CanPort& port,const Profile& profile)noexcept;
 Supervisor(const Supervisor&)=delete;Supervisor& operator=(const Supervisor&)=delete;
 void begin()noexcept;void poll()noexcept;
 Time open_session(Time authenticated_principal)noexcept;
 Result request(const Request& request)noexcept;
 bool take_evidence(robot_run::BootEvidence& output)noexcept;
 Status status()const noexcept{return status_;}
 bool position_sample(unsigned axis,std::int64_t& value,Time& tx_at,Time& at)const noexcept;
 Time oldest_configuration_at()const noexcept;
 Time operation_deadline()const noexcept{return phase_until_;}
private:
 enum class Kind:std::uint8_t {Config,Diag,Disable,Enable,Heartbeat};
 struct Evidence{bool valid{false};std::int64_t value{0};Time tx{0},at{0};};
 struct AxisProof{std::array<Evidence,4> sample{};std::array<Evidence,3> positions{};unsigned count{0};std::array<Evidence,7> config{};};
 struct Pending{bool active{false},confirmed{false};Kind kind{Kind::Diag};unsigned axis{0},index{0};Time tx{0},deadline{0};};
 struct Session{Time id{0},principal{0},seq{0},request{0};};
 bool active()const noexcept;bool advance()noexcept;bool health(bool empty=false)noexcept;
 bool fresh(const Evidence& e,Time ttl)const noexcept;bool stopped()const noexcept;bool configs()const noexcept;
 bool mask(bool selected)const noexcept;bool claim()const noexcept;bool eligible_stop()const noexcept;
 bool send(const robot_core::mks::EncodeResult& f,Kind kind,unsigned axis,unsigned index)noexcept;
 void receive(const robot_can::RxFrame& frame)noexcept;void schedule()noexcept;
 void record_fault(Error error,Time at)noexcept;void abort_stop(Error error)noexcept;
 void fail(Error e,bool premise_lost=false)noexcept;void stop(Error e,bool fault)noexcept;void stop_poll(bool first)noexcept;
 bool add(Time duration,Time& output)noexcept;Time id()noexcept;
 unsigned expected(unsigned axis,unsigned config_index)const noexcept;
 robot_can::CanPort& port_;Profile profile_;robot_can::StopLink stop_link_;Status status_{};
 std::array<AxisProof,2> proof_{};std::array<Session,2> sessions_{};std::array<std::array<Time,11>,2> last_{};
 Pending pending_{};std::array<robot_can::RxFrame,32> raw_{};unsigned raw_head_{0};
 Time last_clock_{0},last_poll_{0},operation_at_{0},phase_until_{0},tx_until_{0},next_send_{0},next_id_{1};
 Time lease_{0},principal_{0},unloaded_until_{0},torque_ack_{0},stop_until_{0},prep_until_{0},isolate_until_{0};
 unsigned config_cursor_{0},diag_cursor_{0},refresh_cursor_{0},target_{0},disabled_mask_{0},heartbeat_mask_{0};
 bool begun_{false},inflight_{false},maintenance_{false},maintenance_done_{false},finished_{false},await_readback_{false},need_config_{false},touched_{false},premise_lost_{false},stop_fault_{false},prep_seen_{false};
};
} // namespace robot_boot
