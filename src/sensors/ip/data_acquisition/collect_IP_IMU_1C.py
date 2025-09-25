import sys
import serial
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
import numpy as np
import time

# Setup serial
ser = serial.Serial('COM3', 115200, timeout=1)

# Setup pyqtgraph
app = QtWidgets.QApplication([])
win = pg.GraphicsLayoutWidget(show=True)
plot = win.addPlot(title="Voltage generated from 98uA @ 25KHz")

# Enable grid
plot.showGrid(x=True, y=True)  # Show grid for both x and y axes

# Set pen with increased line thickness (e.g., thickness of 2)
curve = plot.plot(pen=pg.mkPen('y', width=2))  # Yellow color, thickness 2

# Parameters
max_len = 5000
data = np.zeros(max_len)

# Fix the Y-axis range from 0.5 to 0.7
plot.setYRange(-5, 5)

# Add horizontal lines at y=0.5 and y=0.7
line_0_5 = plot.addLine(y=0.51, pen=pg.mkPen('r', width=1))  # Red line at y=0.5
line_0_7 = plot.addLine(y=0.69, pen=pg.mkPen('r', width=1))  # Red line at y=0.7

# Add text annotations above the horizontal lines using TextItem
text_90 = pg.TextItem("90°", anchor=(0.5, 0), color='r')
text_90.setPos(0, 0.515)  # Position above the line at y=0.5
plot.addItem(text_90)

text_180 = pg.TextItem("180°", anchor=(0.5, 0), color='r')
text_180.setPos(0, 0.695)  # Position above the line at y=0.7
plot.addItem(text_180)

# Variables to calculate sampling rate
last_time = time.time()
sample_count = 0
window_size = 1  # Calculate SPS over a 1-second window

# Initialize a buffer to hold the last 100 samples for moving average
moving_average_window = 100
sample_buffer = []

def update():
    global data, curve, sample_count, last_time, sample_buffer

    if ser.in_waiting > 0:
        raw_data = ser.read(ser.in_waiting).decode('ascii').strip().split()
        for value in raw_data:
            try:
                voltage = float(value)

                # Append the new sample to the buffer
                sample_buffer.append(voltage)

                # If we have enough samples, compute the moving average
                if len(sample_buffer) > moving_average_window:
                    sample_buffer.pop(0)  # Remove the oldest sample

                # Calculate the moving average
                if len(sample_buffer) == moving_average_window:
                    filtered_voltage = np.mean(sample_buffer)  # Moving average

                    data = np.roll(data, -1)  # Shift the data
                    data[-1] = filtered_voltage  # Add the filtered value
                    curve.setData(data)  # Update the curve

                    # Increment sample count
                    sample_count += 1

                    # Check if 1 second has passed to calculate SPS
                    current_time = time.time()
                    if current_time - last_time >= window_size:
                        sps = sample_count / (current_time - last_time)
                        print(f"Sampling Rate: {sps:.2f} SPS")
                        sample_count = 0  # Reset sample count
                        last_time = current_time  # Reset time

            except ValueError:
                print("Invalid data received")

timer = QtCore.QTimer()
timer.timeout.connect(update)
timer.start(1)  # Faster updates (10 ms)

# Start the Qt event loop
app.exec_()

# Close the serial port
ser.close()
