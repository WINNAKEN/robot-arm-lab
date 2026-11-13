idf_component_register(SRCS "main.c" INCLUDE_DIRS "."
    REQUIRES esp_driver_uart esp_driver_usb_serial_jtag esp_timer freertos)
target_compile_definitions(${COMPONENT_LIB} PRIVATE
    WRIST138_HARDWARE_PERMIT=$<BOOL:${WRIST138_HARDWARE_PERMIT}>)
