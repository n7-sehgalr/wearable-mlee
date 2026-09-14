add_library(Adafruit_BusIO STATIC
    Adafruit_I2CDevice.cpp
    Adafruit_BusIO_Register.cpp
)

target_include_directories(Adafruit_BusIO PUBLIC
    ${CMAKE_CURRENT_LIST_DIR}
)

target_link_libraries(Adafruit_BusIO PUBLIC Arduino Wire SPI)
