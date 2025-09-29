# QApplication: Appication handler, one and only one needed for each application
# This object holds event loop of application, core loop that governs all interaction in GUI
# Each event - key press or mouse click or movement generates event -> put on event queue -> in event loop each iteration checks queue
# If event waiting -> pass control to specific event handler for that event -> event handler deals with it then pass control back to event loop
# Only one event loop running per application

# QWidget: Basic empty GUI widget

from PyQt5.QtWidgets import QApplication, QMainWindow

# An instance of QApplicaiton
app = QApplication([])

# An instance of QWidget with QWidget()
# QMainWindow -> Pre-made widget, with lots of standard window features like toolbars, menus, dockable widgets, etc.
# Top level widgets are windows, don't have a parent and not nested within another widget
# We can create a window with any widget
window = QMainWindow()

# Widgets without parent, invisible by default. So need to call .show()
# Need at least one window, can have more
# No way to exit currently. App will close when last window closed
window.show()

app.exec()

