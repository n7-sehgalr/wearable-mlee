add_library(Adafruit_Unified_Sensor STATIC
    Adafruit_Sensor.cpp
)

target_include_directories(Adafruit_Unified_Sensor PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(Adafruit_Unified_Sensor PUBLIC fsl_common Arduino)