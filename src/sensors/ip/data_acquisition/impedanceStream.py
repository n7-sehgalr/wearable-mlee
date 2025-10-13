from random import randint

import pyqtgraph as pg
from PyQt6 import QtCore, QtWidgets

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()

        # Temperature vs. time plot

        self.plot_graph = pg.PlotWidget()
        self.setCentralWidget(self.plot_graph)

        # Customizations
        
        self.plot_graph.setBackground("w")

        # Plot lines drawn using QPen, need to create QPen instance for 
        # custom pen and then pass it to the plot() method
        pen = pg.mkPen(color=(255, 0, 0), width=4)
        
        self.plot_graph.setTitle("Temperature vs. Time", color="k", size="20pt")
        self.plot_graph.setLabel("left", "Temperature (°C)")
        self.plot_graph.setLabel("bottom", "Time(min)")

        # Legend - use addLegend() method on PlotWidget object. 
        # Need to provide name for each line when calling plot()
        self.plot_graph.addLegend()
        self.plot_graph.showGrid(x=True, y=True)
        self.plot_graph.setYRange(20, 40)
        # Data
        self.time = list(range(10))
        self.temperature = [randint(20, 40) for _ in range(10)]
        
        # Need a reference for line object to plot dynamically
        self.line = self.plot_graph.plot(self.time, 
                                         self.temperature,
                                         name="Temperature Sensor", 
                                         pen=pen, symbol="o", 
                                         symbolSize=15, 
                                         symbolBrush="b")
        
        # Add timer to simulate new temperature measurements
        self.timer = QtCore.QTimer()
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def update_plot(self):
        # Discard first value, then append 1 value higher at end
        # Effectivly rolls time to left
        self.time = self.time[1:]
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

