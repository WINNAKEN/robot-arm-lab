#pragma once

#include <array>
#include <cstdint>

namespace robot_core::mks {

// This bench profile supports Classical CAN standard data frames, IDs 1 and 2.
// A hardware adapter must reject CAN FD before constructing this representation.
struct Frame {
    std::uint16_t id{};
    std::uint8_t dlc{};
    std::array<std::uint8_t, 8> data{};
    bool extended{};
    bool rtr{};
};

enum class Error : std::uint8_t {
    None,
    InvalidAxis,
    InvalidFlags,
    InvalidDlc,
    UnsupportedCode,
    InvalidChecksum,
    InvalidValue,
};

struct Parsed {
    std::uint16_t axis{};
    std::uint8_t code{};
    std::int64_t value{};
};

struct EncodeResult {
    Error error{Error::None};
    Frame frame{};
    [[nodiscard]] bool ok() const noexcept { return error == Error::None; }
};

struct DecodeResult {
    Error error{Error::None};
    Parsed parsed{};
    [[nodiscard]] bool ok() const noexcept { return error == Error::None; }
};

// Only 0x31 (position), 0x32 (speed), 0xF1 (run state), 0x3A (enable).
[[nodiscard]] EncodeResult build_read(std::uint16_t axis, std::uint8_t code) noexcept;
[[nodiscard]] EncodeResult build_stop(std::uint16_t axis) noexcept;
[[nodiscard]] EncodeResult build_enable(std::uint16_t axis, bool enabled) noexcept;

// Encodes one FD request: speed 5, acc 2, 100 pulses, DIR=dir1.
// Encoding grants no motion permission and performs no transmission or retry.
[[nodiscard]] EncodeResult build_move100(std::uint16_t axis, bool dir1) noexcept;

// Parses 31/32/F1/3A/F3/F7/FD only. A valid device failure status (0) is
// returned as value=0, not as a codec error. No freshness/request correlation
// is inferred. On codec error, parsed is zeroed and must not be consumed.
[[nodiscard]] DecodeResult parse_response(const Frame& frame) noexcept;

}  // namespace robot_core::mks
