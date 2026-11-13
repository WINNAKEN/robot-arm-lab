idf_component_register(SRCS "stop_link.cpp" INCLUDE_DIRS "include" REQUIRES robot_core)
set_target_properties(${COMPONENT_LIB} PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
