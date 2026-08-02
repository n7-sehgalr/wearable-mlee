add_library(SPI STATIC
    SPI.cpp
)

target_include_directories(SPI PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(SPI PUBLIC Arduino)
