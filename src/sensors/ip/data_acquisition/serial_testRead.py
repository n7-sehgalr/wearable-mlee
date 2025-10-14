import serial
import time

# ser = serial.Serial(port='COM3', baudrate=115200, timeout=1)
ser = serial.Serial(port='/dev/ttyACM0', baudrate=115200, timeout=1)


start = time.time()
samples = 0
sps = []

try:
    while True:
        line = ser.readline()
        if line:
            print(line.decode().strip())
            samples += 1
        current = time.time()
        if current - start >= 1.0:
            print(f"Samples per second: {samples}")
            sps.append(samples)
            samples = 0
            start = time.time()
except KeyboardInterrupt:
    print(f"Samples per second: {sps}")
    
    

        
        