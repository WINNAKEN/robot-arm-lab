idf_component_register(SRCS "wire.cpp" "owner.cpp" INCLUDE_DIRS "include" REQUIRES robot_boot robot_run)
set_target_properties(${COMPONENT_LIB} PROPERTIES CXX_STANDARD 17 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
