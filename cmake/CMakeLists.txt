# SPDX-License-Identifier: Apache-2.0
# Copyright Contributors to the RMTC Project

cmake_minimum_required(VERSION 3.27)

# Set python version explictly
set(PYTHON_VERSION          "3.9")

# Setup overall install paths
set(INSTALL_HOME            "${CMAKE_INSTALL_PREFIX}/${PROJECT_NAME}/${PROJECT_VERSION}")
set(PYTHON_INSTALL_DIR      "python-${PYTHON_VERSION}")

# Define source directories
set(PROJECT_ROOT            "${CMAKE_CURRENT_SOURCE_DIR}/..")
set(PYTHON_LIB_SRC_DIR      "${PROJECT_ROOT}/src/python/lib/")
set(PYTHON_BIN_SRC_DIR      "${PROJECT_ROOT}/src/python/bin/")
set(RESOURCES_SRC_DIR       "${PROJECT_ROOT}/res/")

# Define install directories
set(BIN_INSTALL_DIR         "${INSTALL_HOME}/bin")
set(PYTHON_BIN_INSTALL_DIR  "${INSTALL_HOME}/bin/${PYTHON_INSTALL_DIR}")
set(PYTHON_LIB_INSTALL_DIR  "${INSTALL_HOME}/lib/${PYTHON_INSTALL_DIR}")
set(RESOURCES_INSTALL_DIR   "${INSTALL_HOME}/res")
set(CONFIG_INSTALL_DIR      "${INSTALL_HOME}/res/config")
set(SCRIPTS_INSTALL_DIR     "${INSTALL_HOME}")

# Find the python files and the lib files over
install(DIRECTORY ${PYTHON_LIB_SRC_DIR}
    DESTINATION ${PYTHON_LIB_INSTALL_DIR}
    FILES_MATCHING PATTERN "*.py"
)

# Copy over resources directly
install(DIRECTORY ${RESOURCES_SRC_DIR}
    DESTINATION ${RESOURCES_INSTALL_DIR}
)

# Find the python files and install as programs
file(GLOB PYTHON_BINS "${PYTHON_BIN_SRC_DIR}/*")
install(PROGRAMS ${PYTHON_BINS}
    DESTINATION ${PYTHON_BIN_INSTALL_DIR}
)

# Create the setup script through substituting vars
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/rmtc-setup.csh.in
    ${CMAKE_BINARY_DIR}/rmtc-setup.csh
    @ONLY
)
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/rmtc-setup.bash.in
    ${CMAKE_BINARY_DIR}/rmtc-setup.bash
    @ONLY
)
file(GLOB SCRIPTS "${CMAKE_BINARY_DIR}/rmtc-setup.*")
install(PROGRAMS ${SCRIPTS}
    DESTINATION ${SCRIPTS_INSTALL_DIR}
)
