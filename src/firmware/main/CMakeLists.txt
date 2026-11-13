idf_component_register(
    SRCS "app_main.cpp" "phone_http.cpp" "phone_runtime.cpp"
    INCLUDE_DIRS "."
    PRIV_REQUIRES robot_core robot_can robot_twai robot_phone esp_common log esp_http_server esp_wifi esp_event esp_netif esp_timer nvs_flash esp_hw_support bootloader_support
    EMBED_TXTFILES "../components/robot_phone/web/index.html" "../components/robot_phone/web/app.js"
    REQUIRED_IDF_TARGETS esp32s3
)

set_target_properties(${COMPONENT_LIB} PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)
