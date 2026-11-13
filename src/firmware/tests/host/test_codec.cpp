#include "test_support.hpp"
#include "robot_core/mks_codec.hpp"

#include <array>
#include <cstddef>
#include <cstdint>

namespace {
using namespace robot_core::mks;
constexpr std::array<std::uint16_t, 2> axes{1, 2};
constexpr std::array<std::uint16_t, 7> invalid_axes{0, 3, 255, 256, 0x7FF, 0x800, 0xFFFF};

void check_zero_frame(const Frame& frame) {
    CHECK(frame.id == 0);
    CHECK(frame.dlc == 0);
    CHECK(!frame.extended);
    CHECK(!frame.rtr);
    for (const auto byte : frame.data) {
        CHECK(byte == 0);
    }
}

void check_encode_error(const EncodeResult& result, Error error) {
    CHECK(!result.ok());
    CHECK(result.error == error);
    check_zero_frame(result.frame);
}

void check_decode_error(const DecodeResult& result, Error error) {
    CHECK(!result.ok());
    CHECK(result.error == error);
    CHECK(result.parsed.axis == 0);
    CHECK(result.parsed.code == 0);
    CHECK(result.parsed.value == 0);
}

void check_frame(const EncodeResult& result, const Frame& expected) {
    CHECK(result.ok());
    CHECK(result.error == Error::None);
    CHECK(result.frame.id == expected.id);
    CHECK(result.frame.dlc == expected.dlc);
    CHECK(result.frame.data == expected.data);
    CHECK(result.frame.extended == expected.extended);
    CHECK(result.frame.rtr == expected.rtr);
}

void check_parsed(const Frame& frame, std::int64_t value) {
    const auto result = parse_response(frame);
    CHECK(result.ok());
    CHECK(result.error == Error::None);
    CHECK(result.parsed.axis == frame.id);
    CHECK(result.parsed.code == frame.data[0]);
    CHECK(result.parsed.value == value);
}

// Independent test-data repair, never calls the production encoder/checksum.
// Used to isolate value/code/ID validation from checksum rejection.
void repair_checksum(Frame& frame) {
    unsigned total = frame.id;
    for (unsigned i = 0; i + 1U < frame.dlc; ++i) {
        total += frame.data[i];
    }
    const std::size_t checksum_index = static_cast<std::size_t>(frame.dlc) - 1U;
    frame.data[checksum_index] = static_cast<std::uint8_t>(total % 256U);
}

void known_requests() {
    // Literal references from payloads.json / Makerbase V1.0.9 evidence.
    // Expected bytes are independent of the production checksum routine.
    check_frame(build_read(1, 0x31), {1, 2, {0x31, 0x32}, false, false});
    check_frame(build_read(2, 0x31), {2, 2, {0x31, 0x33}, false, false});
    check_frame(build_read(1, 0x32), {1, 2, {0x32, 0x33}, false, false});
    check_frame(build_read(2, 0x32), {2, 2, {0x32, 0x34}, false, false});
    check_frame(build_read(1, 0xF1), {1, 2, {0xF1, 0xF2}, false, false});
    check_frame(build_read(2, 0xF1), {2, 2, {0xF1, 0xF3}, false, false});
    check_frame(build_read(1, 0x3A), {1, 2, {0x3A, 0x3B}, false, false});
    check_frame(build_read(2, 0x3A), {2, 2, {0x3A, 0x3C}, false, false});
    check_frame(build_stop(1), {1, 2, {0xF7, 0xF8}, false, false});
    check_frame(build_stop(2), {2, 2, {0xF7, 0xF9}, false, false});
    check_frame(build_enable(1, true), {1, 3, {0xF3, 0x01, 0xF5}, false, false});
    check_frame(build_enable(2, true), {2, 3, {0xF3, 0x01, 0xF6}, false, false});
    check_frame(build_enable(1, false), {1, 3, {0xF3, 0x00, 0xF4}, false, false});
    check_frame(build_enable(2, false), {2, 3, {0xF3, 0x00, 0xF5}, false, false});
    check_frame(build_move100(1, false),
                {1, 8, {0xFD, 0x00, 0x05, 0x02, 0x00, 0x00, 0x64, 0x69}, false, false});
    check_frame(build_move100(2, false),
                {2, 8, {0xFD, 0x00, 0x05, 0x02, 0x00, 0x00, 0x64, 0x6A}, false, false});
    check_frame(build_move100(1, true),
                {1, 8, {0xFD, 0x80, 0x05, 0x02, 0x00, 0x00, 0x64, 0xE9}, false, false});
    check_frame(build_move100(2, true),
                {2, 8, {0xFD, 0x80, 0x05, 0x02, 0x00, 0x00, 0x64, 0xEA}, false, false});
}

void invalid_requests() {
    for (const auto axis : invalid_axes) {
        check_encode_error(build_read(axis, 0x31), Error::InvalidAxis);
        check_encode_error(build_stop(axis), Error::InvalidAxis);
        check_encode_error(build_enable(axis, false), Error::InvalidAxis);
        check_encode_error(build_enable(axis, true), Error::InvalidAxis);
        check_encode_error(build_move100(axis, false), Error::InvalidAxis);
        check_encode_error(build_move100(axis, true), Error::InvalidAxis);
    }
    for (const auto axis : axes) {
        for (unsigned code = 0; code < 256; ++code) {
            const auto result = build_read(axis, static_cast<std::uint8_t>(code));
            if (code == 0x31 || code == 0x32 || code == 0xF1 || code == 0x3A) {
                CHECK(result.ok());
            } else {
                check_encode_error(result, Error::UnsupportedCode);
            }
        }
    }
}

void signed_boundaries() {
    struct Example {
        Frame frame;
        std::int64_t value;
    };
    // Explicit two's-complement wire values; 48-bit and 16-bit limits plus
    // adjacent values, non-symmetric byte order, zero and +/-1.
    const Example examples[] = {
        {{1, 8, {0x31, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x32}}, 0},
        {{1, 8, {0x31, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x33}}, 1},
        {{1, 8, {0x31, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x2C}}, -1},
        {{1, 8, {0x31, 0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xAC}}, 140737488355327LL},
        {{1, 8, {0x31, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0xB2}}, -140737488355328LL},
        {{1, 8, {0x31, 0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFE, 0xAB}}, 140737488355326LL},
        {{1, 8, {0x31, 0x80, 0x00, 0x00, 0x00, 0x00, 0x01, 0xB3}}, -140737488355327LL},
        {{1, 8, {0x31, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x47}}, 1108152157446LL},
        {{1, 8, {0x31, 0xFE, 0xFD, 0xFC, 0xFB, 0xFA, 0xFA, 0x18}}, -1108152157446LL},
        {{1, 4, {0x32, 0x00, 0x00, 0x33}}, 0},
        {{1, 4, {0x32, 0x00, 0x01, 0x34}}, 1},
        {{1, 4, {0x32, 0xFF, 0xFF, 0x31}}, -1},
        {{1, 4, {0x32, 0x7F, 0xFF, 0xB1}}, 32767},
        {{1, 4, {0x32, 0x80, 0x00, 0xB3}}, -32768},
        {{1, 4, {0x32, 0x7F, 0xFE, 0xB0}}, 32766},
        {{1, 4, {0x32, 0x80, 0x01, 0xB4}}, -32767},
        {{1, 4, {0x32, 0x12, 0x34, 0x79}}, 4660},
        {{1, 4, {0x32, 0xED, 0xCC, 0xEC}}, -4660},
        {{2, 8, {0x31, 0x7F, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xAD}}, 140737488355327LL},
        {{2, 8, {0x31, 0x80, 0x00, 0x00, 0x00, 0x00, 0x00, 0xB3}}, -140737488355328LL},
        {{2, 4, {0x32, 0x7F, 0xFF, 0xB2}}, 32767},
        {{2, 4, {0x32, 0x80, 0x00, 0xB4}}, -32768},
    };
    for (const auto& example : examples) {
        check_parsed(example.frame, example.value);
    }
}

void known_status_responses() {
    check_parsed({1, 3, {0x3A, 0x01, 0x3C}}, 1);
    check_parsed({2, 3, {0x3A, 0x01, 0x3D}}, 1);
    check_parsed({1, 3, {0xF1, 0x01, 0xF3}}, 1);
    check_parsed({2, 3, {0xF1, 0x01, 0xF4}}, 1);
    check_parsed({1, 3, {0xF3, 0x01, 0xF5}}, 1);
    check_parsed({2, 3, {0xF3, 0x01, 0xF6}}, 1);
    check_parsed({1, 3, {0xF7, 0x01, 0xF9}}, 1);
    check_parsed({2, 3, {0xF7, 0x01, 0xFA}}, 1);
    check_parsed({1, 3, {0xFD, 0x01, 0xFF}}, 1);
    check_parsed({2, 3, {0xFD, 0x01, 0x00}}, 1);
    check_parsed({1, 3, {0xFD, 0x02, 0x00}}, 2);
    check_parsed({2, 3, {0xFD, 0x02, 0x01}}, 2);
    check_parsed({1, 3, {0xFD, 0x00, 0xFE}}, 0);
    check_parsed({2, 3, {0xFD, 0x00, 0xFF}}, 0);
    // A response that reports failure is still a well-formed response.
    check_parsed({1, 3, {0xF1, 0x00, 0xF2}}, 0);
    check_parsed({1, 3, {0xF3, 0x00, 0xF4}}, 0);
    check_parsed({1, 3, {0xF7, 0x00, 0xF8}}, 0);
}

void status_domains() {
    constexpr std::array<std::uint8_t, 5> codes{0xF1, 0x3A, 0xF3, 0xF7, 0xFD};
    for (const auto axis : axes) {
        for (const auto code : codes) {
            for (unsigned value = 0; value < 256; ++value) {
                Frame frame{axis, 3, {code, static_cast<std::uint8_t>(value)}};
                repair_checksum(frame);
                const bool allowed = code == 0xF1 ? value <= 6 :
                    code == 0xFD ? (value == 0 || value == 1 || value == 2 || value == 3 || value == 5) :
                    (value == 0 || value == 1);
                if (allowed) {
                    check_parsed(frame, static_cast<std::int64_t>(value));
                } else {
                    check_decode_error(parse_response(frame), Error::InvalidValue);
                }
            }
        }
    }
}

void malformed_responses() {
    const Frame examples[] = {
        {1, 8, {0x31, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x47}},
        {2, 4, {0x32, 0x7F, 0xFF, 0xB2}},
        {1, 3, {0xF1, 0x01, 0xF3}},
        {2, 3, {0x3A, 0x01, 0x3D}},
        {1, 3, {0xF3, 0x01, 0xF5}},
        {2, 3, {0xF7, 0x01, 0xFA}},
        {1, 3, {0xFD, 0x02, 0x00}},
    };
    for (const auto& valid : examples) {
        CHECK(parse_response(valid).ok());
        for (unsigned dlc = 0; dlc < 256; ++dlc) {
            if (dlc == valid.dlc) {
                continue;
            }
            auto frame = valid;
            frame.dlc = static_cast<std::uint8_t>(dlc);
            check_decode_error(parse_response(frame), Error::InvalidDlc);
        }
        for (unsigned flags = 1; flags <= 3; ++flags) {
            auto frame = valid;
            frame.extended = (flags & 1U) != 0;
            frame.rtr = (flags & 2U) != 0;
            check_decode_error(parse_response(frame), Error::InvalidFlags);
        }
        for (const auto axis : invalid_axes) {
            auto frame = valid;
            frame.id = axis;
            repair_checksum(frame);
            check_decode_error(parse_response(frame), Error::InvalidAxis);
        }
        // Any single-bit mutation in payload/checksum must be rejected.
        for (std::size_t index = 0; index < valid.dlc; ++index) {
            for (unsigned bit = 0; bit < 8; ++bit) {
                auto frame = valid;
                frame.data[index] ^= static_cast<std::uint8_t>(1U << bit);
                const auto result = parse_response(frame);
                CHECK(!result.ok());
                if (index != 0) {
                    CHECK(result.error == Error::InvalidChecksum);
                }
            }
        }
        // Bytes beyond DLC are not part of the wire frame or its checksum.
        auto padded = valid;
        for (std::size_t index = padded.dlc; index < padded.data.size(); ++index) {
            padded.data[index] = 0xFF;
        }
        const auto result = parse_response(padded);
        CHECK(result.ok());
        CHECK(result.parsed.value == parse_response(valid).parsed.value);
    }
    for (unsigned code = 0; code < 256; ++code) {
        if (code == 0x31 || code == 0x32 || code == 0xF1 || code == 0x3A ||
            code == 0xF3 || code == 0xF7 || code == 0xFD) {
            continue;
        }
        Frame frame{1, 3, {static_cast<std::uint8_t>(code), 0x01}};
        repair_checksum(frame);
        check_decode_error(parse_response(frame), Error::UnsupportedCode);
    }
    // A checksum bound to ID1 cannot be accepted as a response from ID2.
    check_decode_error(parse_response({2, 3, {0xF7, 0x01, 0xF9}}), Error::InvalidChecksum);
}

}  // namespace

void run_codec_tests() {
    known_requests();
    invalid_requests();
    signed_boundaries();
    known_status_responses();
    status_domains();
    malformed_responses();
}
