from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QGroupBox, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal

class StaticCalibrationDialog(QDialog):
    """Rich UI Dialog for static BNO055 calibration with EEPROM persistence."""
    
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BNO055 IMU Calibration Guide")
        self.resize(600, 450)
        
        main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>Hardware Calibration Status</h2>"
                        "Calibration runs automatically in the background. Follow the steps below until all bars turn green (3/3).")
        header.setWordWrap(True)
        main_layout.addWidget(header)
        
        # Grid layout for the 4 sensors
        grid = QGridLayout()
        main_layout.addLayout(grid)
        
        # Helper to create a sensor row
        def create_sensor_row(row: int, name: str, instructions: str):
            lbl_name = QLabel(f"<b>{name}</b>")
            lbl_name.setMinimumWidth(100)
            
            lbl_inst = QLabel(instructions)
            lbl_inst.setWordWrap(True)
            lbl_inst.setStyleSheet("color: #555;")
            
            pbar = QProgressBar()
            pbar.setMaximum(3)
            pbar.setValue(0)
            pbar.setFormat("%v / 3")
            pbar.setMinimumWidth(100)
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }") # Default red
            
            grid.addWidget(lbl_name, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(lbl_inst, row, 1, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(pbar, row, 2, Qt.AlignmentFlag.AlignTop)
            
            return pbar

        self.pb_gyro = create_sensor_row(0, "Gyroscope", "Leave the device completely still on a flat surface for a few seconds.")
        self.pb_accel = create_sensor_row(1, "Accelerometer", "Place the device in 6 different orientations (the 6 faces of a cube). Hold it still for 2-3 seconds in each position. If it gets stuck, tilt it 45 degrees briefly.")
        self.pb_mag = create_sensor_row(2, "Magnetometer", "Wave the device in the air in a 'Figure 8' pattern.")
        self.pb_sys = create_sensor_row(3, "System", "This will automatically reach 3/3 when the sensors above are fully calibrated.")
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Saved Calibration")
        self.btn_load.clicked.connect(self.load_requested.emit)
        
        self.btn_save = QPushButton("Save Calibration to PC")
        self.btn_save.clicked.connect(self.save_requested.emit)
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)
        
        self.btn_start = QPushButton("Start Session (Bypass)")
        self.btn_start.setMinimumHeight(40)
        self.btn_start.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_start)

    def _update_bar(self, pbar: QProgressBar, val: int):
        pbar.setValue(val)
        if val == 3:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }") # Green
        elif val > 0:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }") # Orange
        else:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }") # Red

    def update_calib(self, sys_cal: int, gyro: int, accel: int, mag: int):
        self._update_bar(self.pb_sys, sys_cal)
        self._update_bar(self.pb_gyro, gyro)
        self._update_bar(self.pb_accel, accel)
        self._update_bar(self.pb_mag, mag)
        
        if sys_cal == 3 and gyro == 3 and accel == 3 and mag == 3:
            self.btn_start.setText("Start Session (Fully Calibrated)")
            self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        else:
            self.btn_start.setText("Start Session (Bypass)")
            self.btn_start.setStyleSheet("")
            
    def show_loaded_status(self):
        """When calibration is loaded from JSON, update the button."""
        self.btn_start.setText("Start Session (Calib Loaded)")
        self.btn_start.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
