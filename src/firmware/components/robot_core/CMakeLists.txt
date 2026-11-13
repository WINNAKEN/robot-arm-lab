idf_component_register(
    SRCS "mks_codec.cpp" "stop_coordinator.cpp"
    INCLUDE_DIRS "include"
)

set_target_properties(${COMPONENT_LIB} PROPERTIES
    CXX_STANDARD 17
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)
