import serial
import csv
import time
 
import numpy as np
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
 
# === Configuration ===
COM_PORT = 'COM3'      # Change to your serial port
BAUD_RATE = 115200
OUTPUT_FILE = 'combined_output5.csv'
 
# === CSV Headers ===
headers = [
    "Timestamp",                                     # Timestamp in milliseconds
    "Voltage 1", "Impedance 1", "Phase 1",           # Channel 1 readings
]
 
# === Initialize serial port ===
try:
    ser = serial.Serial(COM_PORT, BAUD_RATE, timeout=1)
    print(f"Connected to {COM_PORT} at {BAUD_RATE} baud.")
except serial.SerialException:
    print(f"Error: Could not open serial port {COM_PORT}")
    exit(1)
 
# === Open CSV File ===
csvfile = open(OUTPUT_FILE, 'w', newline='')
writer = csv.writer(csvfile)
writer.writerow(headers)
 
# === PyQtGraph Setup ===
app = QtWidgets.QApplication([])
 
win = pg.GraphicsLayoutWidget(title="Real-Time Impedance Plot (Z1-Z4) with Moving Average")
win.resize(800, 500)
plot = win.addPlot(title="Real-Time Impedance Plot generated from 98uA @ 62.5KHz")
plot.showGrid(x=True, y=True)
plot.setLabel('left', 'Impedance')
plot.setLabel('bottom', 'Samples')
 
colors = ['r', 'g', 'b', 'y']
curves = [plot.plot(pen=pg.mkPen(color, width=2)) for color in colors]
 
# Data buffers for moving average (larger than display window)
MAX_POINTS = 1000
data_buffers = [np.zeros(MAX_POINTS) for _ in range(4)]  # Z1-Z4
ptr = 0  # data index
 
line_buffer = []
 
# Moving average settings
ma_window_size = 30
 
# Sampling rate calculation
last_time = time.time()
sample_count = 0
window_size = 1  # seconds
 
def update():
    global ptr, line_buffer, sample_count, last_time
 
    while ser.in_waiting:
        raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
 
        if raw_line.startswith("#BNO:"):
            bno_data = raw_line[5:].split(',')
            if len(line_buffer) == 1 and len(bno_data) == 13:
                timestamp_ms = int(time.time() * 1000)
                vi_data = line_buffer[0]
 
                # Save to CSV
                combined_row = [timestamp_ms] + vi_data + bno_data
                writer.writerow(combined_row)
 
                try:
                    z_vals = [float(vi_data[1]), float(vi_data[4]), float(vi_data[7]), float(vi_data[10])]
                    #phase_vals = [float(vi_data[8]), float(vi_data[9]), float(vi_data[10]), float(vi_data[11])]
                except ValueError:
                    z_vals = [0, 0, 0, 0]
                    #phase_vals = [0, 0, 0, 0]  # fallback zeros if conversion fails
 
                # Shift and append new data
                for i in range(4):
                    data_buffers[i] = np.roll(data_buffers[i], -1)
                    data_buffers[i][-1] = z_vals[i]
 
                ptr = min(ptr + 1, MAX_POINTS)
 
                # Apply moving average if enough data
                if ptr >= ma_window_size:
                    filt_data = []
                    for i in range(4):
                        filt = np.convolve(data_buffers[i], np.ones(ma_window_size)/ma_window_size, mode='valid')
                        filt_data.append(filt)
                    # Plot filtered data (aligned to length)
                    for i in range(4):
                        curves[i].setData(filt_data[i])
                else:
                    # Plot raw data if not enough for MA
                    for i in range(4):
                        curves[i].setData(data_buffers[i][:ptr])
 
                # Sampling rate tracking
                sample_count += 1
                current_time = time.time()
                if current_time - last_time >= window_size:
                    sps = sample_count / (current_time - last_time)
                    print(f"Sampling Rate: {sps:.2f} SPS")
                    sample_count = 0
                    last_time = current_time
 
                line_buffer = []
 
        else:
            vi_data = raw_line.split(',')
            if len(vi_data) == 12:
                line_buffer = [vi_data]
 
timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(10)
 
win.show()
 
try:
    QtWidgets.QApplication.instance().exec_()
except KeyboardInterrupt:
    print("\nInterrupted by user.")
finally:
    ser.close()
    csvfile.close()
    print(f"\nLogging complete. Data saved to '{OUTPUT_FILE}'")