# SPDX-License-Identifier: MIT
# C++ Firmware Sample for Crispy Bootloader

cmake_minimum_required(VERSION 3.13)

# Auto-download Pico SDK if PICO_SDK_PATH is not set
if(NOT DEFINED ENV{PICO_SDK_PATH} AND NOT PICO_SDK_PATH)
    set(PICO_SDK_FETCH_FROM_GIT ON)
    set(PICOTOOL_FORCE_FETCH_FROM_GIT ON)
endif()

include(pico_sdk_import.cmake)

project(crispy-fw-sample-cpp C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(crispy-fw-sample-cpp
    main.cpp
)

target_link_libraries(crispy-fw-sample-cpp
    pico_runtime
)

# Skip timer alarm pool initialization (causes hw_claim assertion)
target_compile_definitions(crispy-fw-sample-cpp PRIVATE
    PICO_TIME_DEFAULT_ALARM_POOL_DISABLED=1
)

# RAM execution (no flash) - SDK provides linker script for 0x20000000
pico_set_binary_type(crispy-fw-sample-cpp no_flash)

# Disable USB and UART stdio (we're a simple blinky)
pico_enable_stdio_usb(crispy-fw-sample-cpp 0)
pico_enable_stdio_uart(crispy-fw-sample-cpp 0)

# Generate BIN manually (skip picotool which rejects custom RAM layout)
find_program(OBJCOPY arm-none-eabi-objcopy)
add_custom_command(TARGET crispy-fw-sample-cpp POST_BUILD
    COMMAND ${OBJCOPY} -O binary $<TARGET_FILE:crispy-fw-sample-cpp> ${CMAKE_CURRENT_BINARY_DIR}/crispy-fw-sample-cpp.bin
    COMMENT "Generating crispy-fw-sample-cpp.bin"
)
