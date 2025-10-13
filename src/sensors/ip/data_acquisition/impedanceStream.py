# Pyqtgraph native to Qt, uses QGraphicsScene. 
# Therefore, more efficient than matplotlib

import pyqtgraph as pg
from PyQt6 import QtWidgets

# Create PlotWidget instance. All plots in pyqtgraph use this class

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

        self.plot_graph.setXRange(1, 10)
        self.plot_graph.setYRange(20, 40)
        # Data
        time = [1, 2, 3, 4, 5, 6, 7, 8 ,9, 10]
        temperature = [30, 32, 34, 33, 32, 31, 35, 34, 32, 30]
        self.plot_graph.plot(time, temperature, name="Temperature Sensor", pen=pen, symbol="o", symbolSize=15, symbolBrush="b")

app = QtWidgets.QApplication([])
main = MainWindow()
main.show()
app.exec()

