#include "robot_core/mks_codec.hpp"

#include <cstddef>

namespace robot_core::mks {
namespace {

bool valid_axis(std::uint16_t axis) noexcept {
    return axis == 1 || axis == 2;
}

bool readable(std::uint8_t code) noexcept {
    return code == 0x31 || code == 0x32 || code == 0xF1 || code == 0x3A;
}

std::uint8_t response_dlc(std::uint8_t code) noexcept {
    switch (code) {
        case 0x31: return 8;
        case 0x32: return 4;
        case 0xF1:
        case 0x3A:
        case 0xF3:
        case 0xF7:
        case 0xFD: return 3;
        default: return 0;
    }
}

// Called only with a validated DLC and an axis in the restricted 1/2 profile.
std::uint8_t checksum(const Frame& frame) noexcept {
    std::uint16_t sum = frame.id;
    for (std::size_t i = 0; i + 1 < frame.dlc; ++i) {
        sum = static_cast<std::uint16_t>(sum + frame.data[i]);
    }
    return static_cast<std::uint8_t>(sum & 0xFFU);
}

EncodeResult finish(Frame frame) noexcept {
    const std::size_t checksum_index = static_cast<std::size_t>(frame.dlc) - 1U;
    frame.data[checksum_index] = checksum(frame);
    return {Error::None, frame};
}

// The unsigned value is at most 48 bits, so the int64 conversion and the
// subtraction both remain representable. No signed shift/sign-extension cast.
std::int64_t signed_be(const Frame& frame, std::size_t bytes) noexcept {
    std::uint64_t raw = 0;
    for (std::size_t i = 0; i < bytes; ++i) {
        raw = (raw << 8U) | frame.data[i + 1];
    }
    const std::uint64_t modulus = std::uint64_t{1} << (bytes * 8U);
    const std::int64_t value = static_cast<std::int64_t>(raw);
    return (raw & (modulus >> 1U)) != 0
        ? value - static_cast<std::int64_t>(modulus)
        : value;
}

bool valid_status(std::uint8_t code, std::uint8_t value) noexcept {
    switch (code) {
        case 0xF1: return value <= 6;
        case 0x3A:
        case 0xF3:
        case 0xF7: return value <= 1;
        case 0xFD: return value <= 3 || value == 5;
        default: return false;
    }
}

}  // namespace

EncodeResult build_read(std::uint16_t axis, std::uint8_t code) noexcept {
    if (!valid_axis(axis)) {
        return {Error::InvalidAxis, {}};
    }
    if (!readable(code)) {
        return {Error::UnsupportedCode, {}};
    }
    Frame frame{};
    frame.id = axis;
    frame.dlc = 2;
    frame.data[0] = code;
    return finish(frame);
}

EncodeResult build_stop(std::uint16_t axis) noexcept {
    if (!valid_axis(axis)) {
        return {Error::InvalidAxis, {}};
    }
    Frame frame{};
    frame.id = axis;
    frame.dlc = 2;
    frame.data[0] = 0xF7;
    return finish(frame);
}

EncodeResult build_enable(std::uint16_t axis, bool enabled) noexcept {
    if (!valid_axis(axis)) {
        return {Error::InvalidAxis, {}};
    }
    Frame frame{};
    frame.id = axis;
    frame.dlc = 3;
    frame.data[0] = 0xF3;
    frame.data[1] = enabled ? 1 : 0;
    return finish(frame);
}

EncodeResult build_move100(std::uint16_t axis, bool dir1) noexcept {
    if (!valid_axis(axis)) {
        return {Error::InvalidAxis, {}};
    }
    Frame frame{};
    frame.id = axis;
    frame.dlc = 8;
    frame.data = {0xFD, static_cast<std::uint8_t>(dir1 ? 0x80 : 0x00),
                  0x05, 0x02, 0x00, 0x00, 0x64, 0x00};
    return finish(frame);
}

DecodeResult parse_response(const Frame& frame) noexcept {
    if (frame.extended || frame.rtr) {
        return {Error::InvalidFlags, {}};
    }
    if (!valid_axis(frame.id)) {
        return {Error::InvalidAxis, {}};
    }
    if (frame.dlc < 2 || frame.dlc > frame.data.size()) {
        return {Error::InvalidDlc, {}};
    }
    const std::uint8_t code = frame.data[0];
    const std::uint8_t expected_dlc = response_dlc(code);
    if (expected_dlc == 0) {
        return {Error::UnsupportedCode, {}};
    }
    if (frame.dlc != expected_dlc) {
        return {Error::InvalidDlc, {}};
    }
    const std::size_t checksum_index = static_cast<std::size_t>(frame.dlc) - 1U;
    if (frame.data[checksum_index] != checksum(frame)) {
        return {Error::InvalidChecksum, {}};
    }
    if (code == 0x31 || code == 0x32) {
        return {Error::None, {frame.id, code, signed_be(frame, code == 0x31 ? 6 : 2)}};
    }
    if (!valid_status(code, frame.data[1])) {
        return {Error::InvalidValue, {}};
    }
    return {Error::None, {frame.id, code, frame.data[1]}};
}

}  // namespace robot_core::mks
