# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

cmake_minimum_required(VERSION 3.27)
project(RMTC VERSION "0.0.0")
add_subdirectory(cmake)

include(GNUInstallDirs)

if(NOT EXISTS "${CMAKE_INSTALL_PREFIX}")
    message(FATAL_ERROR
        "CMAKE_INSTALL_PREFIX does not exist: ${CMAKE_INSTALL_PREFIX}\n"
        "Please create it or choose a writable directory.")
endif()
