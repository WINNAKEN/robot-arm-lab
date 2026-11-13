#pragma once
// Minimal test double declarations, matched against pinned ESP-IDF 5.5.6.
// This header is used ONLY by host stub tests, never by the target build.
#include "esp_err.h"
#include <cstdint>

using TickType_t = std::uint32_t;
enum gpio_num_t { GPIO_NUM_NC = -1, GPIO_NUM_15 = 15, GPIO_NUM_16 = 16 };
constexpr int ESP_INTR_FLAG_LEVEL1 = 1 << 1;
#define TWAI_IO_UNUSED static_cast<gpio_num_t>(-1)
enum twai_mode_t { TWAI_MODE_NORMAL, TWAI_MODE_NO_ACK, TWAI_MODE_LISTEN_ONLY };
enum twai_state_t { TWAI_STATE_STOPPED, TWAI_STATE_RUNNING, TWAI_STATE_BUS_OFF, TWAI_STATE_RECOVERING };
struct twai_obj_t;
using twai_handle_t = twai_obj_t*;
constexpr std::uint32_t TWAI_ALERT_TX_IDLE = 0x1;
constexpr std::uint32_t TWAI_ALERT_TX_SUCCESS = 0x2;
constexpr std::uint32_t TWAI_ALERT_ARB_LOST = 0x80;
constexpr std::uint32_t TWAI_ALERT_ABOVE_ERR_WARN = 0x100;
constexpr std::uint32_t TWAI_ALERT_BUS_ERROR = 0x200;
constexpr std::uint32_t TWAI_ALERT_TX_FAILED = 0x400;
constexpr std::uint32_t TWAI_ALERT_RX_QUEUE_FULL = 0x800;
constexpr std::uint32_t TWAI_ALERT_ERR_PASS = 0x1000;
constexpr std::uint32_t TWAI_ALERT_BUS_OFF = 0x2000;
constexpr std::uint32_t TWAI_ALERT_RX_FIFO_OVERRUN = 0x4000;
constexpr std::uint32_t TWAI_ALERT_TX_RETRIED = 0x8000;
constexpr std::uint32_t TWAI_ALERT_PERIPH_RESET = 0x10000;
struct twai_general_config_t {
    int controller_id;
    twai_mode_t mode;
    gpio_num_t tx_io, rx_io, clkout_io, bus_off_io;
    std::uint32_t tx_queue_len, rx_queue_len, alerts_enabled, clkout_divider;
    int intr_flags;
    struct { std::uint32_t sleep_allow_pd; } general_flags;
};
struct twai_timing_config_t {
    int clk_src;
    std::uint32_t quanta_resolution_hz, brp;
    std::uint8_t prop_seg, tseg_1, tseg_2, sjw, ssp_offset;
    bool triple_sampling;
};
#define TWAI_TIMING_CONFIG_500KBITS() {0, 10000000, 0, 0, 15, 4, 3, 0, false}
struct twai_filter_config_t {
    std::uint32_t acceptance_code, acceptance_mask;
    bool single_filter;
};
#define TWAI_FILTER_CONFIG_ACCEPT_ALL() {0, 0xFFFFFFFFu, true}
struct twai_status_info_t {
    twai_state_t state;
    std::uint32_t msgs_to_tx, msgs_to_rx, tx_error_counter, rx_error_counter;
    std::uint32_t tx_failed_count, rx_missed_count, rx_overrun_count;
    std::uint32_t arb_lost_count, bus_error_count;
};
struct twai_message_t {
    // Public named fields used by production; no SDK union/ABI emulation.
    std::uint32_t extd:1, rtr:1, ss:1, self:1, dlc_non_comp:1, reserved:27;
    std::uint32_t identifier;
    std::uint8_t data_length_code;
    std::uint8_t data[8];
};
extern "C" {
esp_err_t twai_driver_install_v2(const twai_general_config_t*, const twai_timing_config_t*, const twai_filter_config_t*, twai_handle_t*);
esp_err_t twai_driver_uninstall_v2(twai_handle_t);
esp_err_t twai_start_v2(twai_handle_t);
esp_err_t twai_stop_v2(twai_handle_t);
esp_err_t twai_get_status_info_v2(twai_handle_t, twai_status_info_t*);
esp_err_t twai_read_alerts_v2(twai_handle_t, std::uint32_t*, TickType_t);
esp_err_t twai_transmit_v2(twai_handle_t, const twai_message_t*, TickType_t);
esp_err_t twai_receive_v2(twai_handle_t, twai_message_t*, TickType_t);
}
