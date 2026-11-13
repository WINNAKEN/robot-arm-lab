#pragma once
#include "robot_phone/wire.hpp"
#include "robot_boot/supervisor.hpp"
namespace robot_phone {
using Secret=std::array<char,33>;
struct Seed {Time boot{0};Secret pairing{};std::array<Secret,2> credentials{};std::array<Time,2> principals{};};
enum class Phase:std::uint8_t {Boot,RunChecking,Run,Stopping,Terminal};
enum class AdapterFault:std::uint8_t {None,StopQueueLate};
struct Envelope {Time job{0},enqueued_at{0};Listener listener{Listener::Normal};bool pairing{false};Secret credential{};Wire wire{};};
enum class TransferState:std::uint8_t {None,Pending,Granted,Cancelled,Expired,Failed};
struct Result {Time job{0},accepted_at{0},lease{0},ticket{0};Error error{Error::None};unsigned core_error{0};bool paired{false};Secret credential{};
 Time transfer_id{0},transfer_generation{0},pending_until{0},grant_at{0},lease_until{0},sequence_floor{0};TransferState transfer_state{TransferState::None};};
struct Position {bool valid{false};std::int64_t value{0};Time tx_at{0},at{0};};
struct Snapshot {Time boot{0},generation{1},at{0},lease_owner{0},lease_until{0},config_oldest_at{0},fault_at{0},stop_at{0};Phase phase{Phase::Boot};AdapterFault adapter_fault{AdapterFault::None};unsigned core_state{0},core_fault{0};std::uint16_t selected_axis{0};std::array<Position,2> positions{};std::uint8_t axis_count{0},paired_mask{0};bool ready{false},stop_verified{false},core_stop_verified{false},manual_power_cut_required{false},queue_stop_late{false};bool angle_available{false};std::uint16_t angle_joint{0};};
// All methods (including status/session access) belong exclusively to control task.
class Owner {
public:
 Owner(robot_can::CanPort& port,const robot_boot::Profile& profile,const Seed& seed,const std::array<robot_joint::Calibration,2>& calibration={})noexcept;
 void begin()noexcept;
 bool enqueue(const Envelope& request)noexcept;
 void tick()noexcept;
 bool take_result(Listener listener,Time job,Result& result)noexcept;
 Snapshot snapshot()const noexcept{return snapshot_;}
 void revoke_joint_mapping()noexcept{run_.revoke_joint_mapping();publish();}
 unsigned transfer_attempts()const noexcept{return transfer_.attempts;}
private:
 struct Transfer {TransferState state{TransferState::None};unsigned session{0},attempts{0};Time id{0},generation{0},until{0},grant_at{0},lease{0};std::uint16_t axis{0};};
 bool transfer_stop(const Wire& wire,unsigned session)const noexcept;
 void advance_transfer()noexcept;void stop_transfer()noexcept;void transfer_result(Result& out)const noexcept;
 struct Session {bool paired{false};Time boot_session{0},run_session{0},seq{0},request{0},last_rate{0},boot_lease{0};unsigned credits{400};};
 void execute(const Envelope& request,Result& out)noexcept;
 void publish()noexcept;void phase(Phase value)noexcept;bool mint_handoff()noexcept;
 int authenticate(const Secret& credential)const noexcept;
 bool budget(Session& session,Time now)noexcept;
 robot_can::CanPort& port_;robot_boot::Profile profile_;Seed seed_;robot_boot::Supervisor boot_;robot_run::BenchRun run_;
 std::array<Session,2> sessions_{};std::array<Envelope,2> queue_{};std::array<bool,2> pending_{};std::array<Result,2> results_{};std::array<bool,2> result_ready_{};Snapshot snapshot_{};bool run_active_{false},begun_{false},handoff_waiting_{false};Time handoff_before_{0},handoff_generation_{0};Transfer transfer_{};
};
} // namespace robot_phone
