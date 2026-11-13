cmake_minimum_required(VERSION 3.16)

# ST2 preparation target. Build evidence lives in .dev/esp32-can-evidence/.
# Official build-system reference:
# https://docs.espressif.com/projects/esp-idf/en/v5.5.6/esp32s3/api-guides/build-system.html
if(NOT DEFINED ENV{IDF_PATH})
    message(FATAL_ERROR "Load the pinned ESP-IDF v5.5.6 environment before configuring this project.")
endif()

set(IDF_TARGET "esp32s3" CACHE STRING "robot-arm-lab target")
set(COMPONENTS main)

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(robot_arm_lab)

if(NOT IDF_TARGET STREQUAL "esp32s3")
    message(FATAL_ERROR "This preparation skeleton supports only target esp32s3.")
endif()
