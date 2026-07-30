add_library(Adafruit_BNO055 STATIC
    Adafruit_BNO055.cpp
)

target_include_directories(Adafruit_BNO055 PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(Adafruit_BNO055 PUBLIC Adafruit_Unified_Sensor)