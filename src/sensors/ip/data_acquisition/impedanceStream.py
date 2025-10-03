# QApplication: Appication handler, one and only one needed for each application
# This object holds event loop of application, core loop that governs all interaction in GUI
# Each event - key press or mouse click or movement generates event -> put on event queue -> in event loop each iteration checks queue
# If event waiting -> pass control to specific event handler for that event -> event handler deals with it then pass control back to event loop
# Only one event loop running per application

# QWidget: Basic empty GUI widget

from PyQt6.QtCore import QSize, Qt # QSize used to define sizes
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton

from random import choice

window_titles = [
    'My App',
    'My App',
    'Still My App',
    'Something went wrong'
]

# Custom window, use subclass and include setup for window in the __init__
class MainWindow(QMainWindow):
    # Inherits from QMainWindow
    def __init__(self):
        super().__init__()

        self.setWindowTitle("My App")

        # Changed to self.button to allow scope across whole instance i.e. in the methods too
        self.button = QPushButton("Press Me!")

        # Signals - notifications emitted by widgets
        # Slots - receiver of signals, can by any function or method

        # Most widgets have their own signals like for QMainWindow
        self.windowTitleChanged.connect(self.the_window_title_changed)

        # clicked signal connected to slot called the_button_was_clicked
        self.button.setCheckable(True)
        self.button.clicked.connect(self.the_button_was_clicked)
        # If widget signal doesn't provide signal that sends current state, 
        # we need to get it directly from Widget as given in the method definition
        # For example, released signal fires when button released but doesn't send check state
        self.button.released.connect(self.the_button_was_released)
        
        # We can also send data to slots, checkstate in this case
        self.button.clicked.connect(self.the_button_was_toggled)

        self.setCentralWidget(self.button)

    def the_button_was_clicked(self):
        # Change state of widget
        self.button.setText("You already clicked me.")
        
        # To disable button call
        # self.button.setEnabled(False)
        
        # self.setWindowTitle("My oneshot app")


    def the_button_was_toggled(self, check): # Receives check input from the signal
        # Storing state of widget in variables
        self.button_is_checked = check
        print(f"Checkstate from toggle: {self.button_is_checked}")

        # Signals can be chained together
        # One signal can trigger other signals 
        new_window_title = choice(window_titles)
        print("Setting title: %s" % new_window_title)
        self.setWindowTitle(new_window_title)

    def the_button_was_released(self):
        self.button_is_checked = self.button.isChecked()

        print(f"Checkstate from release: {self.button_is_checked}")

    def the_window_title_changed(self, window_title):
        print("Window title changed: %s" %window_title)

        # windowTitleChanged signal only emitted when window title changes
        # If same title set multiple times, signal only fired first time

        if window_title == "Something went wrong":
            self.button.setDisabled(True)

# An instance of QApplicaiton
app = QApplication([])

# An instance of QWidget with QWidget()
# QMainWindow -> Pre-made widget, with lots of standard window features like toolbars, menus, dockable widgets, etc.
# Top level widgets are windows, don't have a parent and not nested within another widget
# We can create a window with any widget
window = MainWindow()

# Widgets without parent, invisible by default. So need to call .show()
# Need at least one window, can have more
# No way to exit currently. App will close when last window closed
window.show()

app.exec()

