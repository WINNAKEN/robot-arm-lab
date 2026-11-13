idf_component_register(SRCS "diagnostic.cpp" INCLUDE_DIRS "include" REQUIRES robot_can robot_core)
set_target_properties(${COMPONENT_LIB} PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
