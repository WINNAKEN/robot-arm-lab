// ST2 buildable CAN connection. The default entry never starts the driver.

#include <cstring>

#include "sdkconfig.h"
#include "esp_idf_version.h"
#include "esp_log.h"
#include "robot_can/stop_link.hpp"
#include "phone_http.hpp"
#include "robot_twai/idf_twai_port.hpp"

#if ESP_IDF_VERSION != ESP_IDF_VERSION_VAL(5, 5, 6)
#error "robot-arm-lab requires the pinned ESP-IDF v5.5.6 build candidate"
#endif

#if !defined(CONFIG_IDF_TARGET_ESP32S3) || !CONFIG_IDF_TARGET_ESP32S3
#error "robot-arm-lab preparation supports only the esp32s3 target"
#endif

namespace {
constexpr char kTag[] = "robot_arm_lab";
// A menuconfig approval record cannot authorize operation in this skeleton.
constexpr bool kHardwareProfileApproved = false;
static_assert(!kHardwareProfileApproved, "ST2 must remain hardware-unapproved");
#if !defined(CONFIG_ROBOT_LAB_PREPARED_RUNTIME) || !CONFIG_ROBOT_LAB_PREPARED_RUNTIME
robot_can::IdfTwaiPort can_port;
robot_can::StopLink stop_link(can_port);
#endif
}  // namespace

extern "C" void app_main(void) {
    const char* const sdk_version = esp_get_idf_version();
    ESP_LOGI(kTag, "SDK=%s; target=%s; preparation skeleton",
             sdk_version, CONFIG_IDF_TARGET);
#if !defined(CONFIG_ROBOT_LAB_PREPARED_RUNTIME) || !CONFIG_ROBOT_LAB_PREPARED_RUNTIME
    ESP_LOGW(kTag, "hardware profile unapproved; CAN driver disabled; web not connected");
    ESP_LOGI(kTag, "prepared CAN link state=%u (idle); no hardware initialized",
             static_cast<unsigned>(stop_link.state()));
#else
    ESP_LOGW(kTag, "prepared owner/HTTP entry; immutable hardware approvals false");
#endif

    // Numeric version macros alone also match development/dirty SDK builds.
    if (std::strcmp(sdk_version, "v5.5.6") != 0 &&
        std::strcmp(sdk_version, "5.5.6") != 0) {
        ESP_LOGE(kTag, "SDK release string differs from v5.5.6; preparation only");
        return;
    }

#if defined(CONFIG_ROBOT_LAB_HARDWARE_PROFILE_APPROVED) && CONFIG_ROBOT_LAB_HARDWARE_PROFILE_APPROVED
    ESP_LOGW(kTag, "Configured approval record ignored; effective approval remains false");
#endif

#if defined(CONFIG_ROBOT_LAB_PREPARED_RUNTIME) && CONFIG_ROBOT_LAB_PREPARED_RUNTIME
    robot_phone::start_prepared_runtime();
#endif
    // Default build starts no network or CAN transport.
    // No coordinator is started and no action/command is sent from this entry.
}
