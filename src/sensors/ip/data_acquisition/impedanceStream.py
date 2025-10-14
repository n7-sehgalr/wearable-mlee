from random import randint

import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

import serial
import time

# ~1305, from serial_readTest.py runs on Windows laptop. 
# 1424 for WSL on Desktop, ~2815 with timeout = 0 (might have empty values)
SAMPLE_RATE = 1305 
FPS = 30 # refresh rate of plot
WINDOW_SIZE = 10 # seconds of data in one display


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Initialize serial
        try:
            self.ser = serial.Serial('COM3', baudrate=115200, timeout=0.01)
            print("Serial port COM3 opened successfully.")
        except serial.SerialException as e:
                print(f"Error opening serial port: {e}")
        
        self.plot_graph = pg.PlotWidget()
        self.setCentralWidget(self.plot_graph)

        # Customizations
        
        self.plot_graph.setBackground("w")

        pen = pg.mkPen(color=(255, 0, 0), width=4)
        
        self.plot_graph.setTitle("Impedance Pneumography, @98.4 uA 25 kHz", color="k", size="20pt")
        self.plot_graph.setLabel("left", "Voltage (V)")
        self.plot_graph.setLabel("bottom", "Time(s)")


        self.plot_graph.showGrid(x=True, y=True)

        # Fix X axis to 10 seconds, auto-scale Y axis
        self.plot_graph.setXRange(0, WINDOW_SIZE)
        self.plot_graph.getViewBox().enableAutoRange(axis=pg.ViewBox.YAxis, enable=True)
        
        # Data
        self.time = list(range(10))
        self.temperature = [randint(20, 40) for _ in range(10)]
        
        # Need a reference for line object to plot dynamically
        self.line = self.plot_graph.plot(self.time, 
                                         self.temperature,
                                         pen=pen, symbol="o", 
                                         symbolSize=15, 
                                         symbolBrush="b")
        
        # For timestamp
        self.start_time = time.time()
        
        # Timer for timeout and updates
        self.timer = QtCore.QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def update_plot(self):
        # Discard first value, then append 1 value higher at end
        # Effectivly rolls time to left
        
        self.time.append(self.time[-1] + 1)
        # Next two lines roll temperature to left, adding random value at end
        self.temperature = self.temperature[1:]
        self.temperature.append(randint(20,40))
        # Instead of random value, actual next value to come for IP. 
        # For time, actual next timestamp
        self.line.setData(self.time, self.temperature)


app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()

