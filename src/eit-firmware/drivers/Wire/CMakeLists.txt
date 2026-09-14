add_library(Wire STATIC
    WireKinetis.cpp
)

target_include_directories(Wire PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(Wire PUBLIC Arduino)
