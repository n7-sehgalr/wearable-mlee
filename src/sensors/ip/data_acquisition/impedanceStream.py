import matplotlib
import random
matplotlib.use('QtAgg')

from PyQt6 import QtCore, QtWidgets
from matplotlib.figure import Figure

# FigureCanvasQTAgg sets up a matplotlib canvas which creates the
# Figure and adds single set of axes to it. It is also a QWidget 
# so it can be embedded into an application

# Plots in PyQt are rendered as bitmap images on the widget 
# and Qt is unaware of position of lines and other elements. 
# Qt mouse events and transforming them to actions in built in matplotlib.
# This is controlled through custom toolbar that can be added with NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

# User defined MplCanvas inheriting from FigureCanvasQTAgg widget
class MplCanvas(FigureCanvasQTAgg):

    # parent receives self from MainWindow
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        # Create three subplots stacked vertically.
        self.axes = fig.subplots(3, 1)
        super().__init__(fig)


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Create the FigureCanvas object with single set of axes
        
        self.canvas = MplCanvas(self, width=5, height=4, dpi=100)
        self.setCentralWidget(self.canvas)

        # Create toolbar, passing canvas as first parameter, parent as second. 
        # Passing in the canvas links toolbar to it allowing it to be controlled
        toolbar = NavigationToolbar(self.canvas, self)

        # QVBoxLayout arranges widgets vertically from top to bottom
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(toolbar)
        layout.addWidget(self.canvas)

        # Create a placeholder widget to hold both toolbar and canvas
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)

        n_data = 50
        self.xdata = list(range(n_data))
        self.ydata = [random.randint(0, 10) for i in range(n_data)]
        # Create data sources for 3 plots
        self.ydata1 = [random.randint(0, 10) for i in range(n_data)]
        self.ydata2 = [random.randint(0, 10) for i in range(n_data)]
        self.ydata3 = [random.randint(0, 10) for i in range(n_data)]

        # We need to store a reference to the plotted line 
        # somewhere so we can apply the new data to it
        self._plot_ref1 = None
        self._plot_ref2 = None
        self._plot_ref3 = None
        self.update_plot()
        
        self.show()

        # timer triggers the redraw by calling update_plot

        self.timer = QtCore.QTimer()

        # Timeout interval in ms
        self.timer.setInterval(0)

        # timer.timeout() signal emitted when timer times out. Returns ID of timer 
        # Here it connects to the update_plot slot and so it activates it each 
        # time a timer times out
        self.timer.timeout.connect(self.update_plot)
        self.timer.start()

    def update_plot(self):
        # Drop off the first y element, append a new one.
        self.ydata1 = self.ydata1[1:] + [random.randint(0, 10)]
        self.ydata2 = self.ydata2[1:] + [random.randint(0, 10)]
        self.ydata3 = self.ydata3[1:] + [random.randint(0, 10)]



        # Note: we no longer need to clear the axis.
        if self._plot_ref1 is None:
            # First time we have no plot reference, so do a normal plot.
            # .plot returns a list of line <reference>s, as we're
            # only getting one we can take the first element.
            plot_refs1 = self.canvas.axes[0].plot(self.xdata, self.ydata1, 'r')
            self._plot_ref1 = plot_refs1[0]
            self.canvas.axes[0].set_ylabel("Plot 1")

            plot_refs2 = self.canvas.axes[1].plot(self.xdata, self.ydata2, 'g')
            self._plot_ref2 = plot_refs2[0]
            self.canvas.axes[1].set_ylabel("Plot 2")

            plot_refs3 = self.canvas.axes[2].plot(self.xdata, self.ydata3, 'b')
            self._plot_ref3 = plot_refs3[0]
            self.canvas.axes[2].set_ylabel("Plot 3")
            self.canvas.axes[2].set_xlabel("Data Points")
        
        else:
            # We have a reference, we can use it to update the data for that line.
            self._plot_ref1.set_ydata(self.ydata1)
            self._plot_ref2.set_ydata(self.ydata2)
            self._plot_ref3.set_ydata(self.ydata3)
            
        # Trigger the canvas to update and redraw.
        self.canvas.draw()




app = QtWidgets.QApplication([])

window = MainWindow()


app.exec()
