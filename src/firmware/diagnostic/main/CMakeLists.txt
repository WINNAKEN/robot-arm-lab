idf_component_register(SRCS "main.cpp" INCLUDE_DIRS "." PRIV_REQUIRES robot_diagnostic robot_twai esp_common freertos REQUIRED_IDF_TARGETS esp32s3)
set_target_properties(${COMPONENT_LIB} PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
