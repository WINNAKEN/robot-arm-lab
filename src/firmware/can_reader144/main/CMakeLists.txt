idf_component_register(SRCS "main.cpp" INCLUDE_DIRS "." REQUIRES driver esp_driver_usb_serial_jtag esp_timer esp_app_format)
target_compile_features(${COMPONENT_LIB} PUBLIC cxx_std_17)
