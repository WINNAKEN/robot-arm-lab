#include "stub_sdk.hpp"
#include <cassert>

struct twai_obj_t { int unused; };
namespace { twai_obj_t object{}; }
namespace stub {
Fixture f;
void reset() { f = Fixture{}; }
void fail_next(const char* operation, esp_err_t result) {
    f.fail_operation = operation;
    f.fail_occurrence = f.call_count[operation] + 1;
    f.fail_result = result;
}
bool enter(const char* operation, twai_handle_t handle = nullptr) {
    if (handle != nullptr) assert(handle == &object && f.installed);
    f.calls.emplace_back(operation);
    const auto n = ++f.call_count[operation];
    return f.fail_operation == operation && f.fail_occurrence == n;
}
} // namespace stub

extern "C" std::int64_t esp_timer_get_time() { return stub::f.micros; }
extern "C" esp_err_t twai_driver_install_v2(const twai_general_config_t* g,
        const twai_timing_config_t* t, const twai_filter_config_t* filter,
        twai_handle_t* handle) {
    auto& f = stub::f;
    if (stub::enter("install")) return f.fail_result;
    assert(!f.installed);
    f.general = *g; f.timing = *t; f.filter = *filter;
    f.status = {}; f.status.state = TWAI_STATE_STOPPED;
    f.alerts = 0; f.rx.clear(); f.installed = true; *handle = &object;
    if (f.after_install) f.after_install();
    return ESP_OK;
}
extern "C" esp_err_t twai_driver_uninstall_v2(twai_handle_t handle) {
    auto& f = stub::f;
    if (stub::enter("uninstall", handle)) return f.fail_result;
    assert(f.status.state == TWAI_STATE_STOPPED || f.status.state == TWAI_STATE_BUS_OFF);
    f.installed = false;
    return ESP_OK;
}
extern "C" esp_err_t twai_start_v2(twai_handle_t handle) {
    auto& f = stub::f;
    if (stub::enter("start", handle)) return f.fail_result;
    assert(f.status.state == TWAI_STATE_STOPPED);
    f.status.state = TWAI_STATE_RUNNING;
    f.status.msgs_to_tx = f.status.msgs_to_rx = 0; f.rx.clear();
    if (f.after_start) f.after_start();
    return ESP_OK;
}
extern "C" esp_err_t twai_stop_v2(twai_handle_t handle) {
    auto& f = stub::f;
    if (stub::enter("stop", handle)) return f.fail_result;
    assert(f.status.state == TWAI_STATE_RUNNING);
    f.status.state = TWAI_STATE_STOPPED;
    f.status.msgs_to_tx = 0; // RX and alerts intentionally survive stop.
    if (f.after_stop) f.after_stop();
    return ESP_OK;
}
extern "C" esp_err_t twai_get_status_info_v2(twai_handle_t handle, twai_status_info_t* out) {
    auto& f = stub::f;
    if (stub::enter("status", handle)) return f.fail_result;
    *out = f.status;
    return ESP_OK;
}
extern "C" esp_err_t twai_read_alerts_v2(twai_handle_t handle, std::uint32_t* out, TickType_t wait) {
    auto& f = stub::f;
    f.alerts_wait = wait;
    if (stub::enter("alerts", handle)) return f.fail_result;
    *out = f.alerts; f.alerts = 0;
    return *out != 0 || f.empty_alert_success ? ESP_OK : ESP_ERR_TIMEOUT;
}
extern "C" esp_err_t twai_transmit_v2(twai_handle_t handle, const twai_message_t* message, TickType_t wait) {
    auto& f = stub::f;
    f.tx_wait = wait;
    if (stub::enter("transmit", handle)) return f.fail_result;
    assert(f.status.state == TWAI_STATE_RUNNING);
    if (f.status.msgs_to_tx != 0) return ESP_FAIL;
    f.sent = *message; f.status.msgs_to_tx = 1;
    if (f.after_transmit) f.after_transmit();
    return ESP_OK;
}
extern "C" esp_err_t twai_receive_v2(twai_handle_t handle, twai_message_t* out, TickType_t wait) {
    auto& f = stub::f;
    f.rx_wait = wait;
    if (stub::enter("receive", handle)) return f.fail_result;
    if (f.rx.empty()) return ESP_ERR_TIMEOUT;
    *out = f.rx.front(); f.rx.pop_front();
    if (f.status.msgs_to_rx > 0) --f.status.msgs_to_rx;
    if (f.after_receive) f.after_receive();
    return ESP_OK;
}
