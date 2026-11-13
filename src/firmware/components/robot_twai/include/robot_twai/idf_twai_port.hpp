#pragma once
#include "robot_can/can_port.hpp"

struct twai_obj_t;

namespace robot_can {
// One task owns this instance and every SDK call. Explicit close is required;
// construction/destruction never touches GPIO or starts/stops a driver.
class IdfTwaiPort final : public CanPort {
public:
    IdfTwaiPort() noexcept = default;
    ~IdfTwaiPort() override = default;
    std::uint64_t now_ms() const noexcept override;
    bool reset_and_start() noexcept override;
    CloseResult close() noexcept override;
    bool read_alerts(std::uint32_t& alerts) noexcept override;
    bool status(PortStatus& status) noexcept override;
    ReceiveResult receive(RxFrame& frame) noexcept override;
    bool submit(const WireFrame& frame, std::uint64_t dispatch_before) noexcept override;
private:
    bool fail() noexcept;
    bool remove_for_reset() noexcept;
    twai_obj_t* handle_{nullptr};
    bool failed_{false};
    bool close_recorded_{false};
    CloseResult close_result_{};
};
} // namespace robot_can
