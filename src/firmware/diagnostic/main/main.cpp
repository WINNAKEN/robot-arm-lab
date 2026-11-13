#include "sdkconfig.h"
#include "esp_idf_version.h"
#include "robot_diagnostic/execution.hpp"
#include "robot_twai/idf_twai_port.hpp"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include <cstdio>
#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5,5,6)
#error "Requires the existing ESP-IDF v5.5.6 preparation environment"
#endif
#if !defined(CONFIG_IDF_TARGET_ESP32S3) || !CONFIG_IDF_TARGET_ESP32S3
#error "ESP32-S3 target only"
#endif
static_assert(CONFIG_FREERTOS_HZ==1000,"Readonly candidate requires verified 1000Hz configuration");
static_assert(pdMS_TO_TICKS(1)>0,"One millisecond must not become zero ticks");
namespace {
constexpr bool kPhysicalReadApproved=false;
static_assert(!kPhysicalReadApproved,"Physical profile remains unapproved");
}
extern "C" void app_main() {
    const robot_diagnostic::Observed unconfirmed{};
    const auto prepared=robot_diagnostic::prepare_profile(unconfirmed,0);
    if constexpr (!kPhysicalReadApproved) {
        std::printf("{\"state\":\"DISABLED\",\"hardware_approved\":false,\"CAN_started\":false,\"profile_readiness\":%u,\"missing\":%lu,\"mismatch\":%lu,\"tick_hz\":%u}\n",static_cast<unsigned>(prepared.readiness),static_cast<unsigned long>(prepared.missing),static_cast<unsigned long>(prepared.mismatch),static_cast<unsigned>(CONFIG_FREERTOS_HZ));
        return;
    }
    // Prepared path only. No menuconfig, serial input or web API grants approval.
    static robot_can::IdfTwaiPort port;
    static robot_diagnostic::Runner runner(port);
    if (!runner.begin(prepared.transport)) return;
    robot_diagnostic::Cadence cadence;
    if(!cadence.begin(runner.schedule_now_ms()))runner.abort_schedule();
    auto wake=xTaskGetTickCount();
    while (!runner.terminal()) {
        robot_diagnostic::service_scheduled_poll(runner,cadence);
        if(runner.terminal())break;
        robot_diagnostic::schedule_wait_result(runner,xTaskDelayUntil(&wake,pdMS_TO_TICKS(1))==pdTRUE);
    }
    // Emit only after close: console I/O cannot stretch an active poll.
    std::printf("{\"state\":%u,\"error\":%u,\"overflow\":%s}\n",static_cast<unsigned>(runner.state()),static_cast<unsigned>(runner.error()),runner.journal_overflow()?"true":"false");
    const auto health=runner.last_status();const auto close=runner.close_result();
    std::printf("{\"last_alerts\":%lu,\"last_bus_state\":%u,\"tx_pending\":%lu,\"rx_pending\":%lu,\"rx_missed\":%lu,\"rx_overrun\":%lu,\"tx_failed\":%lu,\"bus_errors\":%lu,\"arbitration_lost\":%lu,\"close_quiesced\":%s,\"close_healthy\":%s}\n",static_cast<unsigned long>(runner.last_alerts()),static_cast<unsigned>(health.state),static_cast<unsigned long>(health.tx_pending),static_cast<unsigned long>(health.rx_pending),static_cast<unsigned long>(health.rx_missed),static_cast<unsigned long>(health.rx_overrun),static_cast<unsigned long>(health.tx_failed),static_cast<unsigned long>(health.bus_errors),static_cast<unsigned long>(health.arbitration_lost),close.quiesced?"true":"false",close.healthy?"true":"false");
    for (std::size_t i=0;i<runner.event_count();++i) {
        const auto& e=runner.event(i);
        std::printf("{\"kind\":%u,\"error\":%u,\"at_ms\":%llu,\"rx_dequeued_ms\":%llu,\"id\":%lu,\"dlc\":%u,\"ext\":%s,\"rtr\":%s,\"value\":%lld,\"data\":[",static_cast<unsigned>(e.kind),static_cast<unsigned>(e.error),static_cast<unsigned long long>(e.at),static_cast<unsigned long long>(e.dequeued_at),static_cast<unsigned long>(e.frame.id),static_cast<unsigned>(e.frame.dlc),e.frame.extended?"true":"false",e.frame.rtr?"true":"false",static_cast<long long>(e.value));
        for (std::size_t j=0;j<e.frame.data.size();++j) std::printf("%s%u",j?",":"",static_cast<unsigned>(e.frame.data[j]));
        std::puts("]}");
    }
}
