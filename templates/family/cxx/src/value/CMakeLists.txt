add_library(sample_value STATIC value.cpp)
target_compile_features(sample_value PUBLIC cxx_std_20)
target_include_directories(sample_value PUBLIC
    $<BUILD_INTERFACE:${PROJECT_SOURCE_DIR}/include>
    $<INSTALL_INTERFACE:include>)
target_link_libraries(sample_value PRIVATE sample_strict)
