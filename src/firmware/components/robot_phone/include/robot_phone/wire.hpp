#pragma once
#include <array>
#include <cstdint>
#include <string_view>
namespace robot_phone {
using Time=std::uint64_t;
enum class Op:std::uint8_t {Maintenance,MaintenanceRenew,Unloaded,DisableAll,FinishMaintenance,Drive,EnableSelected,Handoff,Acquire,Renew,Arm,Ticket,Move,Release,Stop,JointStep,HandoffAcquire,HandoffResult};
enum class Error:std::uint8_t {None,Malformed,Auth,Host,Origin,Phase,Replay,Busy,Stale,Rate,SessionFull,Core,Denied,Timeout};
enum class Listener:std::uint8_t {Normal,Stop};
struct Wire {Time boot{0},phase{0},seq{0},request{0},lease{0},ticket{0};Op op{Op::Stop};std::uint16_t axis{0};std::uint8_t direction{0};bool unloaded{false};std::uint16_t joint{0};bool radians{false};double angle{0};};
bool parse(std::string_view body,Wire& out) noexcept;
bool equal_secret(std::string_view a,std::string_view b) noexcept;
Error origin_host(Listener listener,std::string_view host,std::string_view origin) noexcept;
// The complete raw header is checked before its terminating fragment reaches SDK.
class HeaderGuard {
public:
 bool feed(const char* bytes,std::size_t size) noexcept;
 bool complete()const noexcept{return complete_;}
 bool failed()const noexcept{return failed_;}
private:
 bool validate()noexcept;
 std::array<char,1024> raw_{};std::size_t used_{0};bool complete_{false},failed_{false};
};
} // namespace robot_phone
