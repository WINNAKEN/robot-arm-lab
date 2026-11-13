#include "robot_twai/idf_twai_port.hpp"
#include "driver/twai.h"
#include "esp_idf_version.h"
#include "esp_timer.h"
#include "sdkconfig.h"
#include <algorithm>
#include <iterator>
#include <limits>

#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5, 5, 6)
#error "This TWAI contract is pinned to ESP-IDF 5.5.6."
#endif
#if !CONFIG_IDF_TARGET_ESP32S3
#error "This pin and timing candidate is only for ESP32-S3."
#endif

namespace robot_can {
namespace {
constexpr std::uint32_t sdk_alerts = TWAI_ALERT_TX_SUCCESS | TWAI_ALERT_TX_FAILED |
    TWAI_ALERT_TX_IDLE | TWAI_ALERT_BUS_OFF | TWAI_ALERT_RX_QUEUE_FULL |
    TWAI_ALERT_RX_FIFO_OVERRUN | TWAI_ALERT_ERR_PASS | TWAI_ALERT_PERIPH_RESET |
    TWAI_ALERT_TX_RETRIED | TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ABOVE_ERR_WARN |
    TWAI_ALERT_ARB_LOST;

std::uint32_t convert_alerts(std::uint32_t raw) noexcept {
    std::uint32_t out = 0;
    const std::uint32_t source[] = {TWAI_ALERT_TX_SUCCESS, TWAI_ALERT_TX_FAILED,
        TWAI_ALERT_TX_IDLE, TWAI_ALERT_BUS_OFF, TWAI_ALERT_RX_QUEUE_FULL,
        TWAI_ALERT_RX_FIFO_OVERRUN, TWAI_ALERT_ERR_PASS, TWAI_ALERT_PERIPH_RESET,
        TWAI_ALERT_TX_RETRIED, TWAI_ALERT_BUS_ERROR, TWAI_ALERT_ABOVE_ERR_WARN,
        TWAI_ALERT_ARB_LOST};
    const std::uint32_t target[] = {TxSuccess, TxFailed, TxIdle, BusOff, RxQueueFull,
        RxFifoOverrun, ErrorPassive, PeripheralReset, TxRetried, BusError,
        AboveErrorWarning, ArbitrationLost};
    for (std::size_t i = 0; i < sizeof(source) / sizeof(source[0]); ++i)
        if ((raw & source[i]) != 0) out |= target[i];
    return out;
}

bool counters_clear(const twai_status_info_t& s) noexcept {
    return s.rx_missed_count == 0 && s.rx_overrun_count == 0 &&
        s.tx_failed_count == 0 && s.bus_error_count == 0 && s.arb_lost_count == 0;
}

bool read_raw_alerts(twai_handle_t handle, std::uint32_t& out) noexcept {
    out = 0;
    const auto result = twai_read_alerts_v2(handle, &out, 0);
    if (result == ESP_ERR_TIMEOUT) { out = 0; return true; }
    return result == ESP_OK;
}
} // namespace

std::uint64_t IdfTwaiPort::now_ms() const noexcept {
    const auto us = esp_timer_get_time();
    return us < 0 ? std::numeric_limits<std::uint64_t>::max()
                  : static_cast<std::uint64_t>(us) / 1000;
}

bool IdfTwaiPort::fail() noexcept { failed_ = true; return false; }

bool IdfTwaiPort::remove_for_reset() noexcept {
    if (handle_ == nullptr) return true;
    twai_status_info_t before{};
    if (twai_get_status_info_v2(handle_, &before) != ESP_OK) return fail();
    if (before.state == TWAI_STATE_RUNNING) {
        if (twai_stop_v2(handle_) != ESP_OK) return fail();
    } else if (before.state != TWAI_STATE_STOPPED) {
        return fail(); // No automatic restart of BUS_OFF or RECOVERING.
    }
    twai_status_info_t stopped{};
    if (twai_get_status_info_v2(handle_, &stopped) != ESP_OK ||
        stopped.state != TWAI_STATE_STOPPED || stopped.msgs_to_tx != 0) return fail();
    if (twai_driver_uninstall_v2(handle_) != ESP_OK) return fail();
    handle_ = nullptr;
    return true;
}

bool IdfTwaiPort::reset_and_start() noexcept {
    if (failed_) return false;
    close_recorded_ = false;
    if (!remove_for_reset()) return false;
    twai_general_config_t general{};
    general.controller_id = 0;
    general.mode = TWAI_MODE_NORMAL;
    general.tx_io = GPIO_NUM_15;
    general.rx_io = GPIO_NUM_16;
    general.clkout_io = TWAI_IO_UNUSED;
    general.bus_off_io = TWAI_IO_UNUSED;
    general.tx_queue_len = 0;
    general.rx_queue_len = 16;
    general.alerts_enabled = sdk_alerts;
    general.intr_flags = ESP_INTR_FLAG_LEVEL1;
    const twai_timing_config_t timing = TWAI_TIMING_CONFIG_500KBITS();
    const twai_filter_config_t filter = TWAI_FILTER_CONFIG_ACCEPT_ALL();
    if (twai_driver_install_v2(&general, &timing, &filter, &handle_) != ESP_OK)
        return fail();
    if (handle_ == nullptr) return fail();
    twai_status_info_t stopped{};
    std::uint32_t alerts = 0;
    if (twai_get_status_info_v2(handle_, &stopped) != ESP_OK ||
        stopped.state != TWAI_STATE_STOPPED || stopped.msgs_to_tx != 0 ||
        stopped.msgs_to_rx != 0 || !counters_clear(stopped) ||
        !read_raw_alerts(handle_, alerts) || alerts != 0) return fail();
    if (twai_start_v2(handle_) != ESP_OK) return fail();
    twai_status_info_t running{};
    if (twai_get_status_info_v2(handle_, &running) != ESP_OK ||
        running.state != TWAI_STATE_RUNNING || running.msgs_to_tx != 0 ||
        !counters_clear(running)) return fail();
    return true;
}

CloseResult IdfTwaiPort::close() noexcept {
    if (close_recorded_) return close_result_;
    close_recorded_ = true;
    bool healthy = !failed_;
    if (handle_ == nullptr) {
        close_result_ = {true, healthy};
        return close_result_;
    }
    twai_status_info_t before{};
    if (twai_get_status_info_v2(handle_, &before) != ESP_OK) {
        fail();
        close_result_ = {false, false};
        return close_result_;
    }
    if (before.msgs_to_tx != 0 || before.msgs_to_rx != 0 || !counters_clear(before))
        healthy = false; // stop clears TX count; do not discard prior evidence.
    if (before.state == TWAI_STATE_RUNNING) {
        if (twai_stop_v2(handle_) != ESP_OK) {
            fail(); close_result_ = {false, false}; return close_result_;
        }
    } else if (before.state == TWAI_STATE_BUS_OFF) {
        healthy = false;
    } else if (before.state != TWAI_STATE_STOPPED) {
        fail(); close_result_ = {false, false}; return close_result_;
    }

    // Observe SW evidence after controller stop, before uninstall frees it.
    // HAL stop may clear not-yet-serviced HW interrupts: this is not a physical
    // or atomic bus-history proof. See the source evidence document.
    std::uint32_t raw_alerts = 0;
    if (!read_raw_alerts(handle_, raw_alerts) ||
        (raw_alerts & ~TWAI_ALERT_TX_IDLE) != 0) healthy = false;
    twai_status_info_t stopped{};
    if (twai_get_status_info_v2(handle_, &stopped) != ESP_OK) {
        fail(); close_result_ = {false, false}; return close_result_;
    }
    if (stopped.state != TWAI_STATE_STOPPED || stopped.msgs_to_tx != 0 ||
        stopped.msgs_to_rx != 0 || !counters_clear(stopped)) healthy = false;
    if (stopped.state != TWAI_STATE_STOPPED && stopped.state != TWAI_STATE_BUS_OFF) {
        fail(); close_result_ = {false, false}; return close_result_;
    }
    if (twai_driver_uninstall_v2(handle_) != ESP_OK) {
        fail(); close_result_ = {false, false}; return close_result_;
    }
    handle_ = nullptr;
    if (!healthy) fail();
    close_result_ = {true, healthy};
    return close_result_;
}

bool IdfTwaiPort::read_alerts(std::uint32_t& out) noexcept {
    out = 0;
    if (failed_ || handle_ == nullptr) return false;
    std::uint32_t raw = 0;
    if (!read_raw_alerts(handle_, raw) || (raw & ~sdk_alerts) != 0) return fail();
    out = convert_alerts(raw);
    return true;
}

bool IdfTwaiPort::status(PortStatus& out) noexcept {
    if (failed_ || handle_ == nullptr) return false;
    twai_status_info_t raw{};
    if (twai_get_status_info_v2(handle_, &raw) != ESP_OK) return fail();
    PortStatus parsed{};
    switch (raw.state) {
    case TWAI_STATE_STOPPED: parsed.state = BusState::Stopped; break;
    case TWAI_STATE_RUNNING: parsed.state = BusState::Running; break;
    case TWAI_STATE_BUS_OFF: parsed.state = BusState::BusOff; break;
    case TWAI_STATE_RECOVERING: parsed.state = BusState::Recovering; break;
    default: return fail();
    }
    parsed.tx_pending = raw.msgs_to_tx;
    parsed.rx_pending = raw.msgs_to_rx;
    parsed.rx_missed = raw.rx_missed_count;
    parsed.rx_overrun = raw.rx_overrun_count;
    parsed.tx_failed = raw.tx_failed_count;
    parsed.bus_errors = raw.bus_error_count;
    parsed.arbitration_lost = raw.arb_lost_count;
    out = parsed;
    return true;
}

ReceiveResult IdfTwaiPort::receive(RxFrame& out) noexcept {
    if (failed_ || handle_ == nullptr) return ReceiveResult::Error;
    twai_message_t raw{};
    const auto result = twai_receive_v2(handle_, &raw, 0);
    const auto dequeued = now_ms();
    if (result == ESP_ERR_TIMEOUT) return ReceiveResult::Empty;
    if (result != ESP_OK || dequeued == std::numeric_limits<std::uint64_t>::max()) {
        fail(); return ReceiveResult::Error;
    }
    out.frame.id = raw.identifier; // Never narrow an untrusted wire ID.
    out.frame.dlc = raw.data_length_code;
    std::copy(std::begin(raw.data), std::end(raw.data), out.frame.data.begin());
    out.frame.extended = raw.extd != 0;
    out.frame.rtr = raw.rtr != 0;
    out.dequeued_at = dequeued;
    return ReceiveResult::Data;
}

bool IdfTwaiPort::submit(const WireFrame& frame, std::uint64_t dispatch_before) noexcept {
    if (failed_ || handle_ == nullptr) return false;
    if (frame.id > 0x7FF || frame.dlc > 8 || frame.extended || frame.rtr) return fail();
    twai_message_t raw{};
    raw.identifier = frame.id;
    raw.data_length_code = frame.dlc;
    std::copy(frame.data.begin(), frame.data.end(), std::begin(raw.data));
    raw.ss = 1;
    const auto before = now_ms();
    if (before >= dispatch_before) return fail();
    const auto result = twai_transmit_v2(handle_, &raw, 0);
    const auto after = now_ms();
    if (result != ESP_OK || after < before || after >= dispatch_before) return fail();
    return true; // Accepted only; the owner must await TX_SUCCESS separately.
}
} // namespace robot_can
