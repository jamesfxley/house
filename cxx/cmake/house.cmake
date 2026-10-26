# SPDX-License-Identifier: MIT
# Generic C++ helpers (AR-8). Include is definition-only, including before project().
# The pinned house revision selects this API.
include_guard(GLOBAL)


macro(_house_cxx_check_arguments HOUSE_CXX_CA_PREFIX HOUSE_CXX_CA_CALL)
    list(LENGTH ${HOUSE_CXX_CA_PREFIX}_UNPARSED_ARGUMENTS HOUSE_CXX_CA_EXTRA)
    if(HOUSE_CXX_CA_EXTRA GREATER 0)
        message(FATAL_ERROR
            "${HOUSE_CXX_CA_CALL}: unrecognised arguments "
            "'${${HOUSE_CXX_CA_PREFIX}_UNPARSED_ARGUMENTS}'")
    endif()
    list(LENGTH ${HOUSE_CXX_CA_PREFIX}_KEYWORDS_MISSING_VALUES
         HOUSE_CXX_CA_EMPTY)
    if(HOUSE_CXX_CA_EMPTY GREATER 0)
        message(FATAL_ERROR
            "${HOUSE_CXX_CA_CALL}: no value given for "
            "'${${HOUSE_CXX_CA_PREFIX}_KEYWORDS_MISSING_VALUES}'")
    endif()
endmacro()

function(_house_cxx_no_extra_arguments HOUSE_CXX_NX_CALL)
    list(LENGTH ARGN HOUSE_CXX_NX_EXTRA)
    if(HOUSE_CXX_NX_EXTRA GREATER 0)
        message(FATAL_ERROR
            "${HOUSE_CXX_NX_CALL}: unrecognised arguments '${ARGN}'")
    endif()
endfunction()

macro(house_cxx_common_settings HOUSE_CXX_ARG_FREESTANDING)
    _house_cxx_no_extra_arguments("house_cxx_common_settings" ${ARGN})
    set(CMAKE_C_STANDARD 11)
    set(CMAKE_C_STANDARD_REQUIRED ON)
    set(CMAKE_C_EXTENSIONS OFF)
    set(CMAKE_CXX_STANDARD 20)
    set(CMAKE_CXX_STANDARD_REQUIRED ON)
    set(CMAKE_CXX_EXTENSIONS OFF)
    set(CMAKE_POSITION_INDEPENDENT_CODE ON)
    set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

    if(${HOUSE_CXX_ARG_FREESTANDING})
        set(CMAKE_C_EXTENSIONS ON)
        set(CMAKE_POSITION_INDEPENDENT_CODE OFF)
    endif()

    include(GNUInstallDirs)
endmacro()

function(house_cxx_add_strict_target HOUSE_CXX_ARG_NAME)
    cmake_parse_arguments(HOUSE_CXX_STRICT ""
        "WERROR;FREESTANDING;VENDOR_SOURCES" "LANGUAGES" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_STRICT "house_cxx_add_strict_target(${HOUSE_CXX_ARG_NAME})")
    if(DEFINED HOUSE_CXX_STRICT_WERROR AND DEFINED HOUSE_CXX_STRICT_VENDOR_SOURCES)
        message(FATAL_ERROR
            "house_cxx_add_strict_target(${HOUSE_CXX_ARG_NAME}): WERROR and "
            "VENDOR_SOURCES are mutually exclusive -- VENDOR_SOURCES is how a "
            "target that compiles vendor code says so, and WERROR is the "
            "override for a caller that has no such flag")
    endif()
    if(NOT DEFINED HOUSE_CXX_STRICT_WERROR)
        set(HOUSE_CXX_STRICT_WERROR ON)
        if(HOUSE_CXX_STRICT_VENDOR_SOURCES)
            set(HOUSE_CXX_STRICT_WERROR OFF)
        endif()
    endif()
    if(NOT HOUSE_CXX_STRICT_LANGUAGES)
        set(HOUSE_CXX_STRICT_LANGUAGES C CXX)
    endif()
    foreach(HOUSE_CXX_STRICT_LANG IN LISTS HOUSE_CXX_STRICT_LANGUAGES)
        if(NOT HOUSE_CXX_STRICT_LANG MATCHES "^(C|CXX)$")
            message(FATAL_ERROR
                "house_cxx_add_strict_target(${HOUSE_CXX_ARG_NAME}): "
                "LANGUAGES must be C or CXX; got '${HOUSE_CXX_STRICT_LANG}'")
        endif()
    endforeach()
    string(REPLACE ";" "," HOUSE_CXX_STRICT_LANGS "${HOUSE_CXX_STRICT_LANGUAGES}")
    if(NOT DEFINED HOUSE_CXX_STRICT_FREESTANDING)
        if(CMAKE_CROSSCOMPILING)
            set(HOUSE_CXX_STRICT_FREESTANDING ON)
        else()
            set(HOUSE_CXX_STRICT_FREESTANDING OFF)
        endif()
    endif()

    add_library(${HOUSE_CXX_ARG_NAME} INTERFACE)

    set(HOUSE_CXX_STRICT_WARNINGS
        -Wall
        -Wextra
        -Wpedantic
        -Wshadow
        -Wconversion
        -Wsign-conversion
        -Wformat=2
        -Werror=format-security
        -Wimplicit-fallthrough
        -Wnull-dereference
        -Wdouble-promotion
        -Wcast-qual
        -Wcast-align
        -Wundef
        -Wunused
        -Wmisleading-indentation
    )

    set(HOUSE_CXX_STRICT_WARNINGS_CXX
        -Wold-style-cast
        -Woverloaded-virtual
        -Wnon-virtual-dtor
        -Wextra-semi
    )

    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
        list(APPEND HOUSE_CXX_STRICT_WARNINGS
            -Wduplicated-cond
            -Wduplicated-branches
            -Wlogical-op
            -Wtrampolines
        )
        list(APPEND HOUSE_CXX_STRICT_WARNINGS_CXX -Wuseless-cast)
    endif()

    if(HOUSE_CXX_STRICT_WERROR)
        list(APPEND HOUSE_CXX_STRICT_WARNINGS -Werror)
    endif()

    set(HOUSE_CXX_STRICT_DIAGNOSTICS "")
    foreach(HOUSE_CXX_STRICT_FLAG IN LISTS HOUSE_CXX_STRICT_WARNINGS)
        list(APPEND HOUSE_CXX_STRICT_DIAGNOSTICS
            $<$<COMPILE_LANGUAGE:${HOUSE_CXX_STRICT_LANGS}>:${HOUSE_CXX_STRICT_FLAG}>)
    endforeach()
    if(CXX IN_LIST HOUSE_CXX_STRICT_LANGUAGES)
        foreach(HOUSE_CXX_STRICT_FLAG IN LISTS HOUSE_CXX_STRICT_WARNINGS_CXX)
            list(APPEND HOUSE_CXX_STRICT_DIAGNOSTICS
                $<$<COMPILE_LANGUAGE:CXX>:${HOUSE_CXX_STRICT_FLAG}>)
        endforeach()
    endif()

    if(HOUSE_CXX_STRICT_VENDOR_SOURCES)
        set_property(TARGET ${HOUSE_CXX_ARG_NAME}
            PROPERTY HOUSE_CXX_SOURCE_DIAGNOSTICS "${HOUSE_CXX_STRICT_DIAGNOSTICS}")
        cmake_language(EVAL CODE "
            cmake_language(DEFER DIRECTORY [[${CMAKE_SOURCE_DIR}]]
                CALL _house_cxx_apply_source_diagnostics [[${HOUSE_CXX_ARG_NAME}]])")
    else()
        foreach(HOUSE_CXX_STRICT_FLAG IN LISTS HOUSE_CXX_STRICT_DIAGNOSTICS)
            target_compile_options(${HOUSE_CXX_ARG_NAME} INTERFACE
                $<BUILD_INTERFACE:${HOUSE_CXX_STRICT_FLAG}>)
        endforeach()
    endif()

    set(HOUSE_CXX_STRICT_HARDEN_COMPILE
        -fstack-protector-strong
    )
    set(HOUSE_CXX_STRICT_HARDEN_DEFINE "")
    set(HOUSE_CXX_STRICT_HARDEN_LINK "")
    set(HOUSE_CXX_STRICT_HARDEN_DROPPED "")

    include(CheckCXXCompilerFlag)
    set(HOUSE_CXX_STRICT_SAVED_REQUIRED "${CMAKE_REQUIRED_FLAGS}")
    string(APPEND CMAKE_REQUIRED_FLAGS " -Werror")
    check_cxx_compiler_flag(-fstack-clash-protection
                            HOUSE_CXX_STRICT_HAVE_STACK_CLASH)
    set(CMAKE_REQUIRED_FLAGS "${HOUSE_CXX_STRICT_SAVED_REQUIRED}")
    if(HOUSE_CXX_STRICT_HAVE_STACK_CLASH)
        list(APPEND HOUSE_CXX_STRICT_HARDEN_COMPILE
             -fstack-clash-protection)
    else()
        list(APPEND HOUSE_CXX_STRICT_HARDEN_DROPPED
            "-fstack-clash-protection (unimplemented for this target)")
    endif()

    if((CMAKE_CXX_COMPILER_ID STREQUAL "GNU" AND
        CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 13)
       OR (CMAKE_CXX_COMPILER_ID MATCHES "Clang" AND
           CMAKE_CXX_COMPILER_VERSION VERSION_GREATER_EQUAL 16))
        list(APPEND HOUSE_CXX_STRICT_HARDEN_COMPILE -fstrict-flex-arrays=3)
    else()
        list(APPEND HOUSE_CXX_STRICT_HARDEN_DROPPED
            "-fstrict-flex-arrays=3 (needs GCC 13+ / Clang 16+)")
    endif()

    if(HOUSE_CXX_STRICT_FREESTANDING)
        list(APPEND HOUSE_CXX_STRICT_HARDEN_DROPPED
            "-D_FORTIFY_SOURCE=3 (needs a hosted libc)"
            "-Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack (no dynamic loader)")
    else()
        list(APPEND HOUSE_CXX_STRICT_HARDEN_COMPILE
            $<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:-U_FORTIFY_SOURCE>
            $<$<CONFIG:Release,RelWithDebInfo,MinSizeRel>:-D_FORTIFY_SOURCE=3>)
        if(NOT CMAKE_CONFIGURATION_TYPES AND NOT CMAKE_BUILD_TYPE)
            list(APPEND HOUSE_CXX_STRICT_HARDEN_DROPPED
                "-D_FORTIFY_SOURCE=3 (no CMAKE_BUILD_TYPE, so no optimisation)")
        endif()
        list(APPEND HOUSE_CXX_STRICT_HARDEN_LINK
            -Wl,-z,relro -Wl,-z,now -Wl,-z,noexecstack)
    endif()

    include(CheckCXXSourceCompiles)
    check_cxx_source_compiles(
        "#include <version>
         #ifndef _LIBCPP_VERSION
         #error Not libc++
         #endif
         int main() { return 0; }"
        HOUSE_CXX_STRICT_HAVE_LIBCXX)
    if(HOUSE_CXX_STRICT_HAVE_LIBCXX)
        list(APPEND HOUSE_CXX_STRICT_HARDEN_DEFINE
            $<$<CONFIG:Debug>:_LIBCPP_HARDENING_MODE=_LIBCPP_HARDENING_MODE_EXTENSIVE>)
    else()
        list(APPEND HOUSE_CXX_STRICT_HARDEN_DEFINE
            $<$<CONFIG:Debug>:_GLIBCXX_ASSERTIONS>)
    endif()

    foreach(HOUSE_CXX_STRICT_FLAG IN LISTS HOUSE_CXX_STRICT_HARDEN_COMPILE)
        target_compile_options(${HOUSE_CXX_ARG_NAME} INTERFACE
            $<BUILD_INTERFACE:$<$<COMPILE_LANGUAGE:${HOUSE_CXX_STRICT_LANGS}>:${HOUSE_CXX_STRICT_FLAG}>>)
    endforeach()
    foreach(HOUSE_CXX_STRICT_ITEM IN LISTS HOUSE_CXX_STRICT_HARDEN_DEFINE)
        target_compile_definitions(${HOUSE_CXX_ARG_NAME} INTERFACE
            $<BUILD_INTERFACE:${HOUSE_CXX_STRICT_ITEM}>)
    endforeach()
    foreach(HOUSE_CXX_STRICT_ITEM IN LISTS HOUSE_CXX_STRICT_HARDEN_LINK)
        target_link_options(${HOUSE_CXX_ARG_NAME} INTERFACE
            $<BUILD_INTERFACE:${HOUSE_CXX_STRICT_ITEM}>)
    endforeach()

    if(HOUSE_CXX_STRICT_HARDEN_DROPPED)
        foreach(HOUSE_CXX_STRICT_ITEM IN LISTS HOUSE_CXX_STRICT_HARDEN_DROPPED)
            message(STATUS
                "${HOUSE_CXX_ARG_NAME}: hardening not applied: ${HOUSE_CXX_STRICT_ITEM}")
        endforeach()
    endif()

    target_compile_options(${HOUSE_CXX_ARG_NAME} INTERFACE
        $<BUILD_INTERFACE:$<$<AND:$<CONFIG:Debug>,$<COMPILE_LANGUAGE:${HOUSE_CXX_STRICT_LANGS}>>:-g3>>
        $<BUILD_INTERFACE:$<$<AND:$<CONFIG:Debug>,$<COMPILE_LANGUAGE:${HOUSE_CXX_STRICT_LANGS}>>:-Og>>
    )
endfunction()

function(_house_cxx_links_strict HOUSE_CXX_LS_TARGET HOUSE_CXX_LS_STRICT HOUSE_CXX_LS_OUT)
    set(HOUSE_CXX_LS_SEEN "")
    get_target_property(HOUSE_CXX_LS_TODO ${HOUSE_CXX_LS_TARGET} LINK_LIBRARIES)
    if(NOT HOUSE_CXX_LS_TODO)
        set(HOUSE_CXX_LS_TODO "")
    endif()
    while(HOUSE_CXX_LS_TODO)
        list(POP_FRONT HOUSE_CXX_LS_TODO HOUSE_CXX_LS_ITEM)
        if(HOUSE_CXX_LS_ITEM MATCHES "^\\$<LINK_ONLY:")
            continue()
        endif()
        if(HOUSE_CXX_LS_ITEM STREQUAL HOUSE_CXX_LS_STRICT)
            set(${HOUSE_CXX_LS_OUT} TRUE PARENT_SCOPE)
            return()
        endif()
        if(HOUSE_CXX_LS_ITEM MATCHES "\\$<")
            string(REGEX REPLACE "[$<>,:]" ";" HOUSE_CXX_LS_WORDS "${HOUSE_CXX_LS_ITEM}")
            if(HOUSE_CXX_LS_STRICT IN_LIST HOUSE_CXX_LS_WORDS)
                message(FATAL_ERROR
                    "${HOUSE_CXX_LS_STRICT}: ${HOUSE_CXX_LS_TARGET} links it through "
                    "the generator expression '${HOUSE_CXX_LS_ITEM}', which the "
                    "warning set cannot follow; link it by name")
            endif()
            continue()
        endif()
        if(NOT TARGET "${HOUSE_CXX_LS_ITEM}" OR HOUSE_CXX_LS_ITEM IN_LIST HOUSE_CXX_LS_SEEN)
            continue()
        endif()
        list(APPEND HOUSE_CXX_LS_SEEN "${HOUSE_CXX_LS_ITEM}")
        get_target_property(HOUSE_CXX_LS_ALIASED "${HOUSE_CXX_LS_ITEM}" ALIASED_TARGET)
        if(HOUSE_CXX_LS_ALIASED)
            if(HOUSE_CXX_LS_ALIASED STREQUAL HOUSE_CXX_LS_STRICT)
                set(${HOUSE_CXX_LS_OUT} TRUE PARENT_SCOPE)
                return()
            endif()
            set(HOUSE_CXX_LS_ITEM "${HOUSE_CXX_LS_ALIASED}")
        endif()
        get_target_property(HOUSE_CXX_LS_NEXT "${HOUSE_CXX_LS_ITEM}" INTERFACE_LINK_LIBRARIES)
        if(HOUSE_CXX_LS_NEXT)
            list(APPEND HOUSE_CXX_LS_TODO ${HOUSE_CXX_LS_NEXT})
        endif()
    endwhile()
    set(${HOUSE_CXX_LS_OUT} FALSE PARENT_SCOPE)
endfunction()

function(_house_cxx_apply_source_diagnostics HOUSE_CXX_ASD_STRICT)
    get_property(HOUSE_CXX_ASD_SET TARGET ${HOUSE_CXX_ASD_STRICT}
        PROPERTY HOUSE_CXX_SOURCE_DIAGNOSTICS)
    set(HOUSE_CXX_ASD_FLAGS "")
    foreach(HOUSE_CXX_ASD_FLAG IN LISTS HOUSE_CXX_ASD_SET)
        list(APPEND HOUSE_CXX_ASD_FLAGS
            "$<$<IN_LIST:${HOUSE_CXX_ASD_STRICT},$<TARGET_PROPERTY:HOUSE_CXX_STRICT_SOURCES>>:${HOUSE_CXX_ASD_FLAG}>")
    endforeach()
    set(HOUSE_CXX_ASD_DONE "")
    set(HOUSE_CXX_ASD_DIRS "${CMAKE_SOURCE_DIR}")
    while(HOUSE_CXX_ASD_DIRS)
        list(POP_FRONT HOUSE_CXX_ASD_DIRS HOUSE_CXX_ASD_CURRENT)
        get_property(HOUSE_CXX_ASD_SUBDIRS DIRECTORY "${HOUSE_CXX_ASD_CURRENT}"
            PROPERTY SUBDIRECTORIES)
        list(APPEND HOUSE_CXX_ASD_DIRS ${HOUSE_CXX_ASD_SUBDIRS})
        get_property(HOUSE_CXX_ASD_TARGETS DIRECTORY "${HOUSE_CXX_ASD_CURRENT}"
            PROPERTY BUILDSYSTEM_TARGETS)
        foreach(HOUSE_CXX_ASD_TARGET IN LISTS HOUSE_CXX_ASD_TARGETS)
            get_target_property(HOUSE_CXX_ASD_TYPE ${HOUSE_CXX_ASD_TARGET} TYPE)
            if(HOUSE_CXX_ASD_TYPE STREQUAL "INTERFACE_LIBRARY")
                continue()
            endif()
            _house_cxx_links_strict(${HOUSE_CXX_ASD_TARGET} ${HOUSE_CXX_ASD_STRICT}
                HOUSE_CXX_ASD_LINKED)
            if(NOT HOUSE_CXX_ASD_LINKED)
                continue()
            endif()
            set_property(TARGET ${HOUSE_CXX_ASD_TARGET}
                APPEND PROPERTY HOUSE_CXX_STRICT_SOURCES ${HOUSE_CXX_ASD_STRICT})
            get_target_property(HOUSE_CXX_ASD_SOURCES ${HOUSE_CXX_ASD_TARGET} SOURCES)
            foreach(HOUSE_CXX_ASD_SOURCE IN LISTS HOUSE_CXX_ASD_SOURCES)
                if(HOUSE_CXX_ASD_SOURCE MATCHES "^\\$<TARGET_OBJECTS:[^$]*>$")
                    continue()
                endif()
                if(HOUSE_CXX_ASD_SOURCE MATCHES "\\$<")
                    message(FATAL_ERROR
                        "${HOUSE_CXX_ASD_STRICT}: cannot apply the warning set to "
                        "the generator-expression source '${HOUSE_CXX_ASD_SOURCE}' "
                        "of ${HOUSE_CXX_ASD_TARGET}")
                endif()
                cmake_path(ABSOLUTE_PATH HOUSE_CXX_ASD_SOURCE
                    BASE_DIRECTORY "${HOUSE_CXX_ASD_CURRENT}" NORMALIZE
                    OUTPUT_VARIABLE HOUSE_CXX_ASD_PATH)
                set(HOUSE_CXX_ASD_KEY "${HOUSE_CXX_ASD_CURRENT}|${HOUSE_CXX_ASD_PATH}")
                if(HOUSE_CXX_ASD_KEY IN_LIST HOUSE_CXX_ASD_DONE)
                    continue()
                endif()
                list(APPEND HOUSE_CXX_ASD_DONE "${HOUSE_CXX_ASD_KEY}")
                set_property(SOURCE "${HOUSE_CXX_ASD_PATH}"
                    DIRECTORY "${HOUSE_CXX_ASD_CURRENT}"
                    APPEND PROPERTY COMPILE_OPTIONS ${HOUSE_CXX_ASD_FLAGS})
            endforeach()
        endforeach()
    endwhile()
endfunction()

function(house_cxx_werror_sources)
    set(HOUSE_CXX_WERROR_SOURCES ${ARGN})
    if(NOT HOUSE_CXX_WERROR_SOURCES)
        message(FATAL_ERROR "house_cxx_werror_sources: no sources given")
    endif()

    foreach(HOUSE_CXX_WERROR_SRC IN LISTS HOUSE_CXX_WERROR_SOURCES)
        if(IS_ABSOLUTE "${HOUSE_CXX_WERROR_SRC}")
            set(HOUSE_CXX_WERROR_RESOLVED "${HOUSE_CXX_WERROR_SRC}")
        elseif(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/${HOUSE_CXX_WERROR_SRC}")
            set(HOUSE_CXX_WERROR_RESOLVED
                "${CMAKE_CURRENT_SOURCE_DIR}/${HOUSE_CXX_WERROR_SRC}")
        else()
            set(HOUSE_CXX_WERROR_RESOLVED
                "${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_WERROR_SRC}")
        endif()
        get_source_file_property(HOUSE_CXX_WERROR_GENERATED
            "${HOUSE_CXX_WERROR_SRC}" GENERATED)
        if(NOT EXISTS "${HOUSE_CXX_WERROR_RESOLVED}"
           AND NOT HOUSE_CXX_WERROR_GENERATED)
            message(FATAL_ERROR
                "house_cxx_werror_sources: no such source: ${HOUSE_CXX_WERROR_SRC}")
        endif()
    endforeach()

    set_property(SOURCE ${HOUSE_CXX_WERROR_SOURCES}
        APPEND PROPERTY COMPILE_OPTIONS -Werror)
endfunction()

macro(house_cxx_enable_sanitizers HOUSE_CXX_ARG_PREFIX)
    _house_cxx_no_extra_arguments("house_cxx_enable_sanitizers" ${ARGN})
    option(${HOUSE_CXX_ARG_PREFIX}_SANITIZE
           "Build host targets with AddressSanitizer + UBSan" OFF)
    if(${HOUSE_CXX_ARG_PREFIX}_SANITIZE)
        if(CMAKE_CROSSCOMPILING)
            message(FATAL_ERROR
                "${HOUSE_CXX_ARG_PREFIX}_SANITIZE is ON in a cross-compiling build. "
                "This helper supports sanitizing the "
                "host tree instead.")
        endif()
        if(NOT (CMAKE_CXX_COMPILER_ID STREQUAL "GNU"
                OR CMAKE_CXX_COMPILER_ID MATCHES "Clang"))
            message(FATAL_ERROR
                "house_cxx_enable_sanitizers: ${CMAKE_CXX_COMPILER_ID} has no "
                "sanitizer support here; a silent skip would report a green run "
                "for a build that checked nothing")
        endif()
        add_compile_options(-fsanitize=address,undefined -fno-omit-frame-pointer
                            -fno-sanitize-recover=all)
        add_link_options(-fsanitize=address,undefined)
        set_property(GLOBAL PROPERTY HOUSE_CXX_SANITIZERS_APPLIED TRUE)
    endif()
endmacro()

macro(house_cxx_enable_gtest)
    _house_cxx_no_extra_arguments("house_cxx_enable_gtest" ${ARGN})
    get_property(HOUSE_CXX_GTEST_SAN_DONE GLOBAL PROPERTY
                 HOUSE_CXX_SANITIZERS_APPLIED)
    if(NOT HOUSE_CXX_GTEST_SAN_DONE)
        get_directory_property(HOUSE_CXX_GTEST_DIR_OPTS COMPILE_OPTIONS)
        string(FIND "${HOUSE_CXX_GTEST_DIR_OPTS}" "-fsanitize"
               HOUSE_CXX_GTEST_DIR_SAN)
        if(HOUSE_CXX_GTEST_DIR_SAN GREATER_EQUAL 0)
            set(HOUSE_CXX_GTEST_SAN_DONE TRUE)
        endif()
    endif()
    if(NOT HOUSE_CXX_GTEST_SAN_DONE)
        get_cmake_property(HOUSE_CXX_GTEST_VARS VARIABLES)
        foreach(HOUSE_CXX_GTEST_VAR IN LISTS HOUSE_CXX_GTEST_VARS)
            if(NOT HOUSE_CXX_GTEST_VAR MATCHES "_SANITIZE$")
                continue()
            endif()
            if("${${HOUSE_CXX_GTEST_VAR}}")
                message(FATAL_ERROR
                    "house_cxx_enable_gtest: ${HOUSE_CXX_GTEST_VAR} is ON but "
                    "no sanitizer flags are in scope yet. Call "
                    "house_cxx_enable_sanitizers() before this macro, or the "
                    "fetched GoogleTest is compiled uninstrumented and ASan's "
                    "container-overflow detector reports false positives "
                    "against it.")
            endif()
        endforeach()
    endif()

    include(CTest)
    enable_testing()
    if(NOT TARGET GTest::gtest_main)
        include(FetchContent)
        FetchContent_Declare(
            googletest
            URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
            URL_HASH SHA256=1f357c27ca988c3f7c6b4bf68a9395005ac6761f034046e9dde0896e3aba00e4
        )
        set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
        set(INSTALL_GTEST OFF CACHE BOOL "" FORCE)
        FetchContent_MakeAvailable(googletest)
    endif()
    include(GoogleTest)
endmacro()

function(house_cxx_install_package)
    cmake_parse_arguments(HOUSE_CXX_PKG "" "PACKAGE;VERSION;NAMESPACE;CONFIG_SNIPPET" "TARGETS;DEPENDS" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_PKG "house_cxx_install_package")

    foreach(HOUSE_CXX_PKG_REQUIRED IN ITEMS PACKAGE VERSION)
        if(NOT HOUSE_CXX_PKG_${HOUSE_CXX_PKG_REQUIRED})
            message(FATAL_ERROR "house_cxx_install_package: ${HOUSE_CXX_PKG_REQUIRED} is required")
        endif()
    endforeach()
    if(NOT HOUSE_CXX_PKG_PACKAGE MATCHES "^[A-Za-z_][A-Za-z0-9_.+-]*$")
        message(FATAL_ERROR "house_cxx_install_package: invalid PACKAGE identity")
    endif()
    if(NOT HOUSE_CXX_PKG_VERSION MATCHES "^[0-9]+\\.[0-9]+\\.[0-9]+$")
        message(FATAL_ERROR "house_cxx_install_package: VERSION must be major.minor.patch")
    endif()
    get_property(HOUSE_CXX_PKG_REGISTERED GLOBAL PROPERTY HOUSE_CXX_PACKAGES)
    if(HOUSE_CXX_PKG_PACKAGE IN_LIST HOUSE_CXX_PKG_REGISTERED)
        message(FATAL_ERROR "house_cxx_install_package: PACKAGE ${HOUSE_CXX_PKG_PACKAGE} is already registered")
    endif()
    set_property(GLOBAL APPEND PROPERTY HOUSE_CXX_PACKAGES ${HOUSE_CXX_PKG_PACKAGE})
    if(NOT HOUSE_CXX_PKG_NAMESPACE)
        message(FATAL_ERROR "house_cxx_install_package: NAMESPACE is required")
    endif()
    if(NOT HOUSE_CXX_PKG_TARGETS)
        message(FATAL_ERROR "house_cxx_install_package: TARGETS is required")
    endif()

    include(GNUInstallDirs)

    string(REGEX REPLACE "([][+.*()^$?|\\\\])" "\\\\\\1"
        HOUSE_CXX_PKG_NS_RE "${HOUSE_CXX_PKG_NAMESPACE}")
    set(HOUSE_CXX_PKG_SEEN "")
    foreach(HOUSE_CXX_PKG_TARGET IN LISTS HOUSE_CXX_PKG_TARGETS)
        string(REGEX REPLACE "^${HOUSE_CXX_PKG_NS_RE}_" ""
            HOUSE_CXX_PKG_EXPORT_NAME "${HOUSE_CXX_PKG_TARGET}")
        if(HOUSE_CXX_PKG_EXPORT_NAME IN_LIST HOUSE_CXX_PKG_SEEN)
            message(FATAL_ERROR
                "house_cxx_install_package: ${HOUSE_CXX_PKG_TARGET} exports as "
                "${HOUSE_CXX_PKG_NAMESPACE}::${HOUSE_CXX_PKG_EXPORT_NAME}, which "
                "another target in TARGETS already claims")
        endif()
        list(APPEND HOUSE_CXX_PKG_SEEN ${HOUSE_CXX_PKG_EXPORT_NAME})
        set_target_properties(${HOUSE_CXX_PKG_TARGET} PROPERTIES
            EXPORT_NAME ${HOUSE_CXX_PKG_EXPORT_NAME})
    endforeach()

    export(TARGETS ${HOUSE_CXX_PKG_TARGETS}
        NAMESPACE ${HOUSE_CXX_PKG_NAMESPACE}::
        FILE ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}Targets.cmake
    )

    install(TARGETS ${HOUSE_CXX_PKG_TARGETS}
        EXPORT ${HOUSE_CXX_PKG_PACKAGE}Targets
        FILE_SET HEADERS DESTINATION ${CMAKE_INSTALL_INCLUDEDIR}
    )

    install(EXPORT ${HOUSE_CXX_PKG_PACKAGE}Targets
        NAMESPACE ${HOUSE_CXX_PKG_NAMESPACE}::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${HOUSE_CXX_PKG_PACKAGE}
    )

    set(HOUSE_CXX_PKG_FIND_DEPS "")
    if(HOUSE_CXX_PKG_DEPENDS)
        set(HOUSE_CXX_PKG_FIND_DEPS "include(CMakeFindDependencyMacro)\n")
        foreach(dep IN LISTS HOUSE_CXX_PKG_DEPENDS)
            string(APPEND HOUSE_CXX_PKG_FIND_DEPS "find_dependency(${dep} CONFIG)\n")
        endforeach()
    endif()

    set(HOUSE_CXX_PKG_SNIPPET "")
    if(HOUSE_CXX_PKG_CONFIG_SNIPPET)
        file(READ "${HOUSE_CXX_PKG_CONFIG_SNIPPET}" HOUSE_CXX_PKG_SNIPPET)
    endif()

    set(HOUSE_CXX_PKG_TEMPLATE "${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}-config.cmake.in")
    file(WRITE "${HOUSE_CXX_PKG_TEMPLATE}"
        "@PACKAGE_INIT@\n\n"
        "${HOUSE_CXX_PKG_FIND_DEPS}"
        "include(\"\${CMAKE_CURRENT_LIST_DIR}/${HOUSE_CXX_PKG_PACKAGE}Targets.cmake\")\n"
        "${HOUSE_CXX_PKG_SNIPPET}"
        "\n"
        "check_required_components(${HOUSE_CXX_PKG_PACKAGE})\n"
    )

    include(CMakePackageConfigHelpers)

    configure_package_config_file(
        "${HOUSE_CXX_PKG_TEMPLATE}"
        ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}Config.cmake
        INSTALL_DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${HOUSE_CXX_PKG_PACKAGE}
    )

    string(REGEX MATCH "^[0-9]+" HOUSE_CXX_PKG_MAJOR "${HOUSE_CXX_PKG_VERSION}")
    if(HOUSE_CXX_PKG_MAJOR EQUAL 0)
        set(HOUSE_CXX_PKG_COMPATIBILITY SameMinorVersion)
    else()
        set(HOUSE_CXX_PKG_COMPATIBILITY SameMajorVersion)
    endif()
    write_basic_package_version_file(
        ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}ConfigVersion.cmake
        VERSION ${HOUSE_CXX_PKG_VERSION}
        COMPATIBILITY ${HOUSE_CXX_PKG_COMPATIBILITY}
    )

    install(FILES
        ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}Config.cmake
        ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_PKG_PACKAGE}ConfigVersion.cmake
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/${HOUSE_CXX_PKG_PACKAGE}
    )
endfunction()

function(house_cxx_add_module_test HOUSE_CXX_ARG_PACKAGE HOUSE_CXX_ARG_MODULE)
    cmake_parse_arguments(HOUSE_CXX_MT "" "NAME" "SOURCES;LIBRARIES" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_MT "house_cxx_add_module_test(${HOUSE_CXX_ARG_MODULE})")
    if(NOT HOUSE_CXX_MT_SOURCES)
        message(FATAL_ERROR
            "house_cxx_add_module_test(${HOUSE_CXX_ARG_PACKAGE} "
            "${HOUSE_CXX_ARG_MODULE}): no SOURCES")
    endif()

    set(HOUSE_CXX_MT_TARGET "${HOUSE_CXX_ARG_PACKAGE}_${HOUSE_CXX_ARG_MODULE}_tests")
    if(HOUSE_CXX_MT_NAME)
        set(HOUSE_CXX_MT_TARGET "${HOUSE_CXX_MT_NAME}")
    endif()

    add_executable(${HOUSE_CXX_MT_TARGET} ${HOUSE_CXX_MT_SOURCES})
    target_compile_features(${HOUSE_CXX_MT_TARGET} PRIVATE cxx_std_20)
    target_link_libraries(${HOUSE_CXX_MT_TARGET} PRIVATE
        ${HOUSE_CXX_ARG_PACKAGE}_strict
        ${HOUSE_CXX_ARG_PACKAGE}::${HOUSE_CXX_ARG_MODULE}
        ${HOUSE_CXX_MT_LIBRARIES}
        GTest::gtest_main
    )
    gtest_discover_tests(${HOUSE_CXX_MT_TARGET}
        TEST_PREFIX "${HOUSE_CXX_ARG_PACKAGE}.")
endfunction()

function(house_cxx_add_doc_examples HOUSE_CXX_ARG_TARGET)
    cmake_parse_arguments(HOUSE_CXX_DE "" "PACKAGE;GROUP;HARNESS_DIR"
                          "DOCUMENTS;GROUP_DOCUMENTS;LIBRARIES;GROUPS" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_DE
        "house_cxx_add_doc_examples(${HOUSE_CXX_ARG_TARGET})")
    if(NOT HOUSE_CXX_DE_PACKAGE OR NOT HOUSE_CXX_DE_DOCUMENTS OR
       NOT HOUSE_CXX_DE_HARNESS_DIR)
        message(FATAL_ERROR
            "house_cxx_add_doc_examples(${HOUSE_CXX_ARG_TARGET}): PACKAGE, "
            "DOCUMENTS and HARNESS_DIR are all required")
    endif()
    if(HOUSE_CXX_DE_GROUP AND NOT HOUSE_CXX_DE_GROUP IN_LIST HOUSE_CXX_DE_GROUPS)
        message(FATAL_ERROR
            "house_cxx_add_doc_examples(${HOUSE_CXX_ARG_TARGET}): GROUP "
            "'${HOUSE_CXX_DE_GROUP}' is not a group; declare it in GROUPS")
    endif()
    if(HOUSE_CXX_DE_GROUP AND HOUSE_CXX_DE_GROUP_DOCUMENTS)
        message(FATAL_ERROR
            "house_cxx_add_doc_examples(${HOUSE_CXX_ARG_TARGET}): "
            "GROUP_DOCUMENTS is the ungrouped call's, naming the documents the "
            "matching GROUP call reads")
    endif()
    set(HOUSE_CXX_DE_GROUP_PATHS "")
    foreach(HOUSE_CXX_DE_FW IN LISTS HOUSE_CXX_DE_GROUP_DOCUMENTS)
        get_filename_component(HOUSE_CXX_DE_FW "${HOUSE_CXX_DE_FW}" ABSOLUTE)
        list(APPEND HOUSE_CXX_DE_GROUP_PATHS "${HOUSE_CXX_DE_FW}")
    endforeach()
    set(HOUSE_CXX_DE_OUT "${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_ARG_TARGET}")
    file(MAKE_DIRECTORY "${HOUSE_CXX_DE_OUT}")
    set(HOUSE_CXX_DE_NAMES "")
    set(HOUSE_CXX_DE_SEEN "")
    foreach(HOUSE_CXX_DE_DOC IN LISTS HOUSE_CXX_DE_DOCUMENTS)
        get_filename_component(HOUSE_CXX_DE_PATH "${HOUSE_CXX_DE_DOC}" ABSOLUTE)
        set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
                     "${HOUSE_CXX_DE_PATH}")
        _house_cxx_doc_examples_read("${HOUSE_CXX_DE_PATH}" "${HOUSE_CXX_DE_DOC}"
                                      "${HOUSE_CXX_DE_OUT}" "${HOUSE_CXX_DE_GROUP}"
                                      HOUSE_CXX_DE_NAMES HOUSE_CXX_DE_SEEN)
    endforeach()
    if(NOT HOUSE_CXX_DE_NAMES)
        set(HOUSE_CXX_DE_IN "")
        if(HOUSE_CXX_DE_GROUP)
            set(HOUSE_CXX_DE_IN " in group '${HOUSE_CXX_DE_GROUP}'")
        endif()
        message(FATAL_ERROR
            "house_cxx_add_doc_examples(${HOUSE_CXX_ARG_TARGET}): no example to "
            "compile${HOUSE_CXX_DE_IN} in ${HOUSE_CXX_DE_DOCUMENTS}")
    endif()

    get_filename_component(HOUSE_CXX_DE_HDIR "${HOUSE_CXX_DE_HARNESS_DIR}" ABSOLUTE)
    file(GLOB HOUSE_CXX_DE_HARNESSES CONFIGURE_DEPENDS "${HOUSE_CXX_DE_HDIR}/*.cpp")
    foreach(HOUSE_CXX_DE_HARNESS IN LISTS HOUSE_CXX_DE_HARNESSES)
        get_filename_component(HOUSE_CXX_DE_STEM "${HOUSE_CXX_DE_HARNESS}" NAME_WE)
        if(NOT HOUSE_CXX_DE_STEM IN_LIST HOUSE_CXX_DE_NAMES)
            message(FATAL_ERROR
                "house_cxx_add_doc_examples: harness ${HOUSE_CXX_DE_HARNESS} "
                "names no example in ${HOUSE_CXX_DE_DOCUMENTS}")
        endif()
    endforeach()
    foreach(HOUSE_CXX_DE_NAME IN LISTS HOUSE_CXX_DE_NAMES)
        if(NOT EXISTS "${HOUSE_CXX_DE_HDIR}/${HOUSE_CXX_DE_NAME}.cpp")
            message(FATAL_ERROR
                "house_cxx_add_doc_examples: example '${HOUSE_CXX_DE_NAME}' has "
                "no harness; add ${HOUSE_CXX_DE_HARNESS_DIR}/${HOUSE_CXX_DE_NAME}.cpp")
        endif()
    endforeach()

    add_library(${HOUSE_CXX_ARG_TARGET} OBJECT ${HOUSE_CXX_DE_HARNESSES})
    target_compile_features(${HOUSE_CXX_ARG_TARGET} PRIVATE cxx_std_20)
    target_include_directories(${HOUSE_CXX_ARG_TARGET} PRIVATE "${HOUSE_CXX_DE_OUT}")
    target_link_libraries(${HOUSE_CXX_ARG_TARGET} PRIVATE
        ${HOUSE_CXX_DE_PACKAGE}_strict ${HOUSE_CXX_DE_LIBRARIES})
endfunction()

function(_house_cxx_doc_examples_read HOUSE_CXX_DR_PATH HOUSE_CXX_DR_DOC
         HOUSE_CXX_DR_OUT HOUSE_CXX_DR_GROUP HOUSE_CXX_DR_NAMES_VAR
         HOUSE_CXX_DR_SEEN_VAR)
    set(HOUSE_CXX_DR_NAMES "${${HOUSE_CXX_DR_NAMES_VAR}}")
    set(HOUSE_CXX_DR_SEEN "${${HOUSE_CXX_DR_SEEN_VAR}}")
    file(READ "${HOUSE_CXX_DR_PATH}" HOUSE_CXX_DR_TEXT)
    string(ASCII 1 HOUSE_CXX_DR_BS)
    string(ASCII 2 HOUSE_CXX_DR_SC)
    string(ASCII 3 HOUSE_CXX_DR_LB)
    string(ASCII 4 HOUSE_CXX_DR_RB)
    if(HOUSE_CXX_DR_TEXT MATCHES "[${HOUSE_CXX_DR_BS}-${HOUSE_CXX_DR_RB}]")
        message(FATAL_ERROR
            "house_cxx_add_doc_examples: ${HOUSE_CXX_DR_DOC} holds a control "
            "character (0x01-0x04), which no document should")
    endif()
    string(REPLACE "\\" "${HOUSE_CXX_DR_BS}" HOUSE_CXX_DR_TEXT "${HOUSE_CXX_DR_TEXT}")
    string(REPLACE ";" "${HOUSE_CXX_DR_SC}" HOUSE_CXX_DR_TEXT "${HOUSE_CXX_DR_TEXT}")
    string(REPLACE "[" "${HOUSE_CXX_DR_LB}" HOUSE_CXX_DR_TEXT "${HOUSE_CXX_DR_TEXT}")
    string(REPLACE "]" "${HOUSE_CXX_DR_RB}" HOUSE_CXX_DR_TEXT "${HOUSE_CXX_DR_TEXT}")
    string(REPLACE "\n" ";" HOUSE_CXX_DR_LINES "${HOUSE_CXX_DR_TEXT}")

    set(HOUSE_CXX_DR_NUMBER 0)
    set(HOUSE_CXX_DR_STATE "prose")      # prose | expect | fenced
    set(HOUSE_CXX_DR_NAME "")            # the marker's name; empty in an unmarked fence
    set(HOUSE_CXX_DR_MINE FALSE)         # whether the fence is compiled by this call
    set(HOUSE_CXX_DR_AT "")
    foreach(HOUSE_CXX_DR_LINE IN LISTS HOUSE_CXX_DR_LINES)
        math(EXPR HOUSE_CXX_DR_NUMBER "${HOUSE_CXX_DR_NUMBER} + 1")
        set(HOUSE_CXX_DR_WHERE "${HOUSE_CXX_DR_DOC}:${HOUSE_CXX_DR_NUMBER}")
        if(HOUSE_CXX_DR_STATE STREQUAL "fenced")
            if(HOUSE_CXX_DR_INDENT AND HOUSE_CXX_DR_LINE MATCHES "^([ \t]*)[^ \t]")
                string(LENGTH "${CMAKE_MATCH_1}" HOUSE_CXX_DR_LEAD)
                string(LENGTH "${HOUSE_CXX_DR_INDENT}" HOUSE_CXX_DR_ILEN)
                if(HOUSE_CXX_DR_LEAD LESS HOUSE_CXX_DR_ILEN)
                    message(FATAL_ERROR
                        "house_cxx_add_doc_examples: ${HOUSE_CXX_DR_WHERE} is "
                        "indented less than its opening fence at "
                        "${HOUSE_CXX_DR_OPENED}; indent it, and the closer, with "
                        "the fence")
                endif()
            endif()
            if(HOUSE_CXX_DR_LINE MATCHES "^[ \t]*(${HOUSE_CXX_DR_FENCE}+)[ \t]*$")
                string(LENGTH "${CMAKE_MATCH_1}" HOUSE_CXX_DR_RUN)
                if(HOUSE_CXX_DR_RUN GREATER_EQUAL HOUSE_CXX_DR_OPEN)
                    if(HOUSE_CXX_DR_CXX AND HOUSE_CXX_DR_MINE)
                        _house_cxx_doc_examples_write("${HOUSE_CXX_DR_OUT}"
                            "${HOUSE_CXX_DR_NAME}" "${HOUSE_CXX_DR_BODY}")
                    endif()
                    set(HOUSE_CXX_DR_STATE "prose")
                    continue()
                endif()
            endif()
            if(HOUSE_CXX_DR_CXX)
                string(LENGTH "${HOUSE_CXX_DR_INDENT}" HOUSE_CXX_DR_ILEN)
                string(SUBSTRING "${HOUSE_CXX_DR_LINE}" 0 ${HOUSE_CXX_DR_ILEN}
                       HOUSE_CXX_DR_HEAD)
                if(HOUSE_CXX_DR_HEAD STREQUAL HOUSE_CXX_DR_INDENT)
                    string(SUBSTRING "${HOUSE_CXX_DR_LINE}" ${HOUSE_CXX_DR_ILEN} -1
                           HOUSE_CXX_DR_LINE)
                endif()
                string(APPEND HOUSE_CXX_DR_BODY "${HOUSE_CXX_DR_LINE}\n")
            endif()
            continue()
        endif()

        set(HOUSE_CXX_DR_OPENS FALSE)
        if(HOUSE_CXX_DR_LINE MATCHES "^([ \t]*)(````*|~~~~*)(.*)$")
            set(HOUSE_CXX_DR_OPENS TRUE)
            set(HOUSE_CXX_DR_INDENT "${CMAKE_MATCH_1}")
            string(LENGTH "${CMAKE_MATCH_2}" HOUSE_CXX_DR_OPEN)
            string(SUBSTRING "${CMAKE_MATCH_2}" 0 1 HOUSE_CXX_DR_FENCE)
            string(STRIP "${CMAKE_MATCH_3}" HOUSE_CXX_DR_INFO)
            set(HOUSE_CXX_DR_LANG "")
            if(HOUSE_CXX_DR_INFO MATCHES "^([^ \t]+)")
                string(TOLOWER "${CMAKE_MATCH_1}" HOUSE_CXX_DR_LANG)
            endif()
            set(HOUSE_CXX_DR_CXX FALSE)
            if(HOUSE_CXX_DR_LANG MATCHES "^(cpp|c\\+\\+|cxx|cc)$")
                set(HOUSE_CXX_DR_CXX TRUE)
            endif()
        endif()

        if(HOUSE_CXX_DR_STATE STREQUAL "expect")
            if(NOT HOUSE_CXX_DR_OPENS OR NOT HOUSE_CXX_DR_CXX)
                message(FATAL_ERROR
                    "house_cxx_add_doc_examples: the marker at ${HOUSE_CXX_DR_AT} "
                    "is not followed by a C++ block")
            endif()
        elseif(HOUSE_CXX_DR_LINE MATCHES
               "^[ \t]*<!-- example: (([a-z0-9_-]+)/)?([A-Za-z0-9_-]+) -->[ \t]*$")
            set(HOUSE_CXX_DR_IN "${CMAKE_MATCH_2}")
            set(HOUSE_CXX_DR_NAME "${CMAKE_MATCH_3}")
            set(HOUSE_CXX_DR_AT "${HOUSE_CXX_DR_WHERE}")
            if(HOUSE_CXX_DR_IN AND NOT HOUSE_CXX_DR_IN IN_LIST HOUSE_CXX_DE_GROUPS)
                message(FATAL_ERROR
                    "house_cxx_add_doc_examples: the marker at ${HOUSE_CXX_DR_AT} "
                    "names unknown group '${HOUSE_CXX_DR_IN}'; declare it in GROUPS")
            endif()
            if(HOUSE_CXX_DR_IN AND NOT HOUSE_CXX_DR_GROUP AND
               NOT HOUSE_CXX_DR_PATH IN_LIST HOUSE_CXX_DE_GROUP_PATHS)
                message(FATAL_ERROR
                    "house_cxx_add_doc_examples: the grouped example at "
                    "${HOUSE_CXX_DR_AT} is in a document not among the "
                    "GROUP_DOCUMENTS, so no matching GROUP call compiles it; "
                    "list ${HOUSE_CXX_DR_DOC} there and in that call's DOCUMENTS")
            endif()
            set(HOUSE_CXX_DR_MINE FALSE)
            if(NOT HOUSE_CXX_DR_NAME STREQUAL "none")
                if(HOUSE_CXX_DR_NAME IN_LIST HOUSE_CXX_DR_SEEN)
                    message(FATAL_ERROR
                        "house_cxx_add_doc_examples: example '${HOUSE_CXX_DR_NAME}' "
                        "at ${HOUSE_CXX_DR_WHERE} is named twice")
                endif()
                list(APPEND HOUSE_CXX_DR_SEEN "${HOUSE_CXX_DR_NAME}")
                if(HOUSE_CXX_DR_IN STREQUAL HOUSE_CXX_DR_GROUP)
                    set(HOUSE_CXX_DR_MINE TRUE)
                    list(APPEND HOUSE_CXX_DR_NAMES "${HOUSE_CXX_DR_NAME}")
                endif()
            endif()
            set(HOUSE_CXX_DR_STATE "expect")
            continue()
        elseif(HOUSE_CXX_DR_OPENS AND HOUSE_CXX_DR_CXX)
            message(FATAL_ERROR
                "house_cxx_add_doc_examples: the C++ block at ${HOUSE_CXX_DR_WHERE} "
                "is not marked; put <!-- example: <name> --> or "
                "<!-- example: none --> on the line above it")
        else()
            set(HOUSE_CXX_DR_NAME "")
            set(HOUSE_CXX_DR_MINE FALSE)
        endif()
        if(HOUSE_CXX_DR_OPENS)
            set(HOUSE_CXX_DR_STATE "fenced")
            set(HOUSE_CXX_DR_BODY "")
            set(HOUSE_CXX_DR_OPENED "${HOUSE_CXX_DR_WHERE}")
        else()
            set(HOUSE_CXX_DR_STATE "prose")
        endif()
    endforeach()
    if(HOUSE_CXX_DR_STATE STREQUAL "expect")
        message(FATAL_ERROR
            "house_cxx_add_doc_examples: the marker at ${HOUSE_CXX_DR_AT} "
            "is not followed by a C++ block")
    endif()
    if(HOUSE_CXX_DR_STATE STREQUAL "fenced" AND HOUSE_CXX_DR_CXX)
        message(FATAL_ERROR
            "house_cxx_add_doc_examples: the C++ block opened at "
            "${HOUSE_CXX_DR_OPENED} is never closed; close it with a run of "
            "the opening character at least as long as the opener")
    endif()
    set(${HOUSE_CXX_DR_NAMES_VAR} "${HOUSE_CXX_DR_NAMES}" PARENT_SCOPE)
    set(${HOUSE_CXX_DR_SEEN_VAR} "${HOUSE_CXX_DR_SEEN}" PARENT_SCOPE)
endfunction()

function(_house_cxx_doc_examples_write HOUSE_CXX_DW_OUT HOUSE_CXX_DW_NAME
         HOUSE_CXX_DW_BODY)
    string(ASCII 1 HOUSE_CXX_DW_BS)
    string(ASCII 2 HOUSE_CXX_DW_SC)
    string(ASCII 3 HOUSE_CXX_DW_LB)
    string(ASCII 4 HOUSE_CXX_DW_RB)
    string(REPLACE "${HOUSE_CXX_DW_RB}" "]" HOUSE_CXX_DW_BODY "${HOUSE_CXX_DW_BODY}")
    string(REPLACE "${HOUSE_CXX_DW_LB}" "[" HOUSE_CXX_DW_BODY "${HOUSE_CXX_DW_BODY}")
    string(REPLACE "${HOUSE_CXX_DW_SC}" ";" HOUSE_CXX_DW_BODY "${HOUSE_CXX_DW_BODY}")
    string(REPLACE "${HOUSE_CXX_DW_BS}" "\\" HOUSE_CXX_DW_BODY "${HOUSE_CXX_DW_BODY}")
    set(HOUSE_CXX_DW_FILE "${HOUSE_CXX_DW_OUT}/${HOUSE_CXX_DW_NAME}.inc")
    set(HOUSE_CXX_DW_OLD "")
    if(EXISTS "${HOUSE_CXX_DW_FILE}")
        file(READ "${HOUSE_CXX_DW_FILE}" HOUSE_CXX_DW_OLD)
    endif()
    if(NOT HOUSE_CXX_DW_OLD STREQUAL HOUSE_CXX_DW_BODY)
        file(WRITE "${HOUSE_CXX_DW_FILE}" "${HOUSE_CXX_DW_BODY}")
    endif()
endfunction()

function(house_cxx_add_fuzzer HOUSE_CXX_ARG_NAME)
    cmake_parse_arguments(HOUSE_CXX_FZ "" "PACKAGE;SOURCE;OUTPUT_DIR;CORPUS;RUNS" "LIBRARIES" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_FZ "house_cxx_add_fuzzer(${HOUSE_CXX_ARG_NAME})")
    if(NOT HOUSE_CXX_FZ_PACKAGE OR NOT HOUSE_CXX_FZ_SOURCE)
        message(FATAL_ERROR
            "house_cxx_add_fuzzer(${HOUSE_CXX_ARG_NAME}): PACKAGE and SOURCE "
            "are both required")
    endif()

    string(TOUPPER "${HOUSE_CXX_FZ_PACKAGE}" HOUSE_CXX_FZ_PREFIX)
    if(NOT ${HOUSE_CXX_FZ_PREFIX}_ENABLE_FUZZERS)
        return()
    endif()

    if(NOT HOUSE_CXX_FZ_CORPUS)
        set(HOUSE_CXX_FZ_CORPUS corpus/${HOUSE_CXX_ARG_NAME})
    endif()
    cmake_path(ABSOLUTE_PATH HOUSE_CXX_FZ_CORPUS BASE_DIRECTORY
        "${CMAKE_CURRENT_SOURCE_DIR}" NORMALIZE)
    if(NOT IS_DIRECTORY "${HOUSE_CXX_FZ_CORPUS}")
        message(FATAL_ERROR
            "house_cxx_add_fuzzer(${HOUSE_CXX_ARG_NAME}): the seed corpus "
            "directory ${HOUSE_CXX_FZ_CORPUS} does not exist; add it, or name "
            "another with CORPUS")
    endif()
    if(NOT DEFINED HOUSE_CXX_FZ_RUNS)
        set(HOUSE_CXX_FZ_RUNS 1000)
    endif()
    if(NOT HOUSE_CXX_FZ_RUNS MATCHES "^[1-9][0-9]*$")
        message(FATAL_ERROR
            "house_cxx_add_fuzzer(${HOUSE_CXX_ARG_NAME}): RUNS must be a "
            "positive integer, not '${HOUSE_CXX_FZ_RUNS}'")
    endif()

    _house_cxx_probe_fuzzer()
    if(NOT HOUSE_CXX_HAS_FUZZER)
        message(WARNING
            "${HOUSE_CXX_FZ_PREFIX}_ENABLE_FUZZERS is ON but the compiler "
            "lacks -fsanitize=fuzzer; skipping fuzz target "
            "${HOUSE_CXX_ARG_NAME}.")
        return()
    endif()

    add_executable(${HOUSE_CXX_ARG_NAME} ${HOUSE_CXX_FZ_SOURCE})
    target_compile_features(${HOUSE_CXX_ARG_NAME} PRIVATE cxx_std_20)
    target_link_libraries(${HOUSE_CXX_ARG_NAME} PRIVATE
        ${HOUSE_CXX_FZ_PACKAGE}_strict
        ${HOUSE_CXX_FZ_LIBRARIES}
    )
    target_compile_options(${HOUSE_CXX_ARG_NAME} PRIVATE -fsanitize=fuzzer,address)
    target_link_options(${HOUSE_CXX_ARG_NAME} PRIVATE -fsanitize=fuzzer,address)
    if(NOT HOUSE_CXX_FZ_OUTPUT_DIR)
        set(HOUSE_CXX_FZ_OUTPUT_DIR ${CMAKE_BINARY_DIR}/fuzzers)
    endif()
    set_target_properties(${HOUSE_CXX_ARG_NAME} PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY ${HOUSE_CXX_FZ_OUTPUT_DIR})

    # Bounded run (libFuzzer -runs, -seed, -artifact_prefix): the first corpus
    # directory receives new inputs, so a build-tree directory goes first and
    # the committed seeds are only read.
    set(HOUSE_CXX_FZ_WORK ${CMAKE_CURRENT_BINARY_DIR}/${HOUSE_CXX_ARG_NAME}_corpus)
    file(MAKE_DIRECTORY "${HOUSE_CXX_FZ_WORK}")
    add_test(NAME ${HOUSE_CXX_ARG_NAME}_bounded_run
        COMMAND ${HOUSE_CXX_ARG_NAME} "${HOUSE_CXX_FZ_WORK}" "${HOUSE_CXX_FZ_CORPUS}"
            -runs=${HOUSE_CXX_FZ_RUNS} -seed=1
            -artifact_prefix=${HOUSE_CXX_FZ_WORK}/)
    set_tests_properties(${HOUSE_CXX_ARG_NAME}_bounded_run PROPERTIES LABELS fuzz)
endfunction()

function(house_cxx_version_definitions HOUSE_CXX_ARG_TARGET
                                        HOUSE_CXX_ARG_PACKAGE
                                        HOUSE_CXX_ARG_SCOPE)
    _house_cxx_no_extra_arguments("house_cxx_version_definitions" ${ARGN})
    string(TOUPPER "${HOUSE_CXX_ARG_PACKAGE}" HOUSE_CXX_VD_PREFIX)
    target_compile_definitions(${HOUSE_CXX_ARG_TARGET} ${HOUSE_CXX_ARG_SCOPE}
        ${HOUSE_CXX_VD_PREFIX}_CMAKE_VERSION_MAJOR=${PROJECT_VERSION_MAJOR}
        ${HOUSE_CXX_VD_PREFIX}_CMAKE_VERSION_MINOR=${PROJECT_VERSION_MINOR}
        ${HOUSE_CXX_VD_PREFIX}_CMAKE_VERSION_PATCH=${PROJECT_VERSION_PATCH}
    )
endfunction()

macro(house_cxx_declare_tests_option HOUSE_CXX_ARG_PREFIX)
    _house_cxx_no_extra_arguments("house_cxx_declare_tests_option" ${ARGN})
    set(${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS_DEFAULT OFF)
    if(PROJECT_IS_TOP_LEVEL AND NOT CMAKE_CROSSCOMPILING)
        set(${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS_DEFAULT ON)
    endif()
    option(${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS
           "Build the host test suite"
           ${${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS_DEFAULT})
endmacro()

macro(house_cxx_declare_install_option HOUSE_CXX_ARG_PREFIX)
    cmake_parse_arguments(HOUSE_CXX_IO "" "AVAILABLE" "" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_IO "house_cxx_declare_install_option(${HOUSE_CXX_ARG_PREFIX})")
    set(HOUSE_CXX_IO_WANTED TRUE)
    if(DEFINED HOUSE_CXX_IO_AVAILABLE AND NOT HOUSE_CXX_IO_AVAILABLE)
        set(HOUSE_CXX_IO_WANTED FALSE)
    endif()
    set(${HOUSE_CXX_ARG_PREFIX}_ENABLE_INSTALL_DEFAULT OFF)
    if(PROJECT_IS_TOP_LEVEL AND HOUSE_CXX_IO_WANTED)
        set(${HOUSE_CXX_ARG_PREFIX}_ENABLE_INSTALL_DEFAULT ON)
    endif()
    option(${HOUSE_CXX_ARG_PREFIX}_ENABLE_INSTALL "Generate install/export rules"
        ${${HOUSE_CXX_ARG_PREFIX}_ENABLE_INSTALL_DEFAULT})
endmacro()

macro(_house_cxx_probe_fuzzer)
    include(CheckCXXCompilerFlag)
    set(HOUSE_CXX_FZ_SAVED_REQUIRED "${CMAKE_REQUIRED_FLAGS}")
    set(CMAKE_REQUIRED_FLAGS "-fsanitize=fuzzer-no-link -Werror")
    check_cxx_compiler_flag("-fsanitize=fuzzer-no-link" HOUSE_CXX_HAS_FUZZER)
    set(CMAKE_REQUIRED_FLAGS "${HOUSE_CXX_FZ_SAVED_REQUIRED}")
endmacro()

macro(house_cxx_declare_fuzzers_option HOUSE_CXX_ARG_PREFIX)
    _house_cxx_no_extra_arguments("house_cxx_declare_fuzzers_option" ${ARGN})
    option(${HOUSE_CXX_ARG_PREFIX}_ENABLE_FUZZERS
           "Build the libFuzzer targets (Clang only)" OFF)
    if(${HOUSE_CXX_ARG_PREFIX}_ENABLE_FUZZERS AND
       NOT ${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS)
        message(FATAL_ERROR
            "${HOUSE_CXX_ARG_PREFIX}_ENABLE_FUZZERS requires "
            "${HOUSE_CXX_ARG_PREFIX}_ENABLE_TESTS=ON: the fuzz targets live in "
            "the test tree.")
    endif()
    if(${HOUSE_CXX_ARG_PREFIX}_ENABLE_FUZZERS)
        _house_cxx_probe_fuzzer()
    endif()
    if(${HOUSE_CXX_ARG_PREFIX}_ENABLE_FUZZERS AND HOUSE_CXX_HAS_FUZZER)
        get_property(HOUSE_CXX_FZ_EXISTING DIRECTORY PROPERTY BUILDSYSTEM_TARGETS)
        foreach(HOUSE_CXX_FZ_TARGET IN LISTS HOUSE_CXX_FZ_EXISTING)
            get_target_property(HOUSE_CXX_FZ_TYPE ${HOUSE_CXX_FZ_TARGET} TYPE)
            if(NOT HOUSE_CXX_FZ_TYPE STREQUAL "INTERFACE_LIBRARY")
                message(FATAL_ERROR
                    "house_cxx_declare_fuzzers_option(${HOUSE_CXX_ARG_PREFIX}) "
                    "runs after target ${HOUSE_CXX_FZ_TARGET}, which would be "
                    "fuzzed without coverage instrumentation or sanitizers. Call "
                    "it before any compiled target is declared.")
            endif()
        endforeach()
        add_compile_options(-fsanitize=fuzzer-no-link,address,undefined
                            -fno-sanitize-recover=all -fno-omit-frame-pointer)
        add_link_options(-fsanitize=address,undefined)
    endif()
endmacro()

macro(house_cxx_declare_enum_option HOUSE_CXX_ARG_PREFIX)
    cmake_parse_arguments(HOUSE_CXX_EN "" "NAME;DEFAULT;DOC" "VALUES" ${ARGN})
    _house_cxx_check_arguments(HOUSE_CXX_EN "house_cxx_declare_enum_option(${HOUSE_CXX_ARG_PREFIX})")
    if(NOT HOUSE_CXX_EN_NAME OR NOT HOUSE_CXX_EN_DEFAULT OR
       NOT HOUSE_CXX_EN_VALUES)
        message(FATAL_ERROR
            "house_cxx_declare_enum_option(${HOUSE_CXX_ARG_PREFIX}): NAME, "
            "DEFAULT and VALUES are all required")
    endif()
    if(NOT HOUSE_CXX_EN_DEFAULT IN_LIST HOUSE_CXX_EN_VALUES)
        message(FATAL_ERROR
            "house_cxx_declare_enum_option(${HOUSE_CXX_ARG_PREFIX}): DEFAULT "
            "'${HOUSE_CXX_EN_DEFAULT}' is not one of VALUES")
    endif()
    if(NOT HOUSE_CXX_EN_DOC)
        set(HOUSE_CXX_EN_DOC
            "${HOUSE_CXX_ARG_PREFIX}_${HOUSE_CXX_EN_NAME}")
    endif()

    set(HOUSE_CXX_EN_VAR "${HOUSE_CXX_ARG_PREFIX}_${HOUSE_CXX_EN_NAME}")
    string(REPLACE ";" ", " HOUSE_CXX_EN_LIST "${HOUSE_CXX_EN_VALUES}")
    set(${HOUSE_CXX_EN_VAR} "${HOUSE_CXX_EN_DEFAULT}" CACHE STRING
        "${HOUSE_CXX_EN_DOC}: one of ${HOUSE_CXX_EN_LIST}")
    set_property(CACHE ${HOUSE_CXX_EN_VAR}
                 PROPERTY STRINGS ${HOUSE_CXX_EN_VALUES})
    if(NOT "${${HOUSE_CXX_EN_VAR}}" IN_LIST HOUSE_CXX_EN_VALUES)
        message(FATAL_ERROR
            "${HOUSE_CXX_EN_VAR} must be one of ${HOUSE_CXX_EN_LIST}; got "
            "'${${HOUSE_CXX_EN_VAR}}'")
    endif()
endmacro()
