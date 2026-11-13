#pragma once
#include "driver/twai.h"
#include <deque>
#include <functional>
#include <map>
#include <string>
#include <vector>

namespace stub {
struct Fixture {
    bool installed{false};
    std::int64_t micros{0};
    twai_general_config_t general{};
    twai_timing_config_t timing{};
    twai_filter_config_t filter{};
    twai_status_info_t status{};
    std::uint32_t alerts{0};
    bool empty_alert_success{false};
    twai_message_t sent{};
    std::deque<twai_message_t> rx{};
    std::vector<std::string> calls{};
    std::map<std::string, unsigned> call_count{};
    std::string fail_operation{};
    unsigned fail_occurrence{0};
    esp_err_t fail_result{ESP_FAIL};
    TickType_t tx_wait{999}, rx_wait{999}, alerts_wait{999};
    std::function<void()> after_install{}, after_start{}, after_stop{}, after_transmit{}, after_receive{};
};
extern Fixture f;
void reset();
void fail_next(const char* operation, esp_err_t result = ESP_FAIL);
}
