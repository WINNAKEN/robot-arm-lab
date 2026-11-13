idf_component_register(
    SRCS "idf_twai_port.cpp"
    INCLUDE_DIRS "include"
    REQUIRES robot_can
    PRIV_REQUIRES driver esp_timer
)
set_target_properties(${COMPONENT_LIB} PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)
