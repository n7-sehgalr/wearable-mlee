from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QProgressBar, QGroupBox, QGridLayout,
                             QTextEdit)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont


class StaticCalibrationDialog(QDialog):
    """Rich UI Dialog for BNO055 calibration with PC-side persistence.
    
    Shows live calibration progress bars, step-by-step instructions,
    and a status log that displays offset values on save/load.
    """
    
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("BNO055 IMU Calibration Guide")
        self.setMinimumSize(620, 520)
        self.resize(620, 520)
        
        main_layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>IMU Calibration</h2>"
                        "The BNO055 calibrates automatically in the background. "
                        "Follow the steps below until all bars turn <b>green (3/3)</b>.")
        header.setWordWrap(True)
        main_layout.addWidget(header)
        
        # Grid layout for the 4 sensors
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)  # instructions column stretches
        main_layout.addLayout(grid)
        
        # Helper to create a sensor row
        def create_sensor_row(row: int, name: str, instructions: str):
            lbl_name = QLabel(f"<b>{name}</b>")
            lbl_name.setMinimumWidth(110)
            
            lbl_inst = QLabel(instructions)
            lbl_inst.setWordWrap(True)
            lbl_inst.setStyleSheet("color: #555;")
            
            pbar = QProgressBar()
            pbar.setMaximum(3)
            pbar.setValue(0)
            pbar.setFormat("%v / 3")
            pbar.setFixedWidth(90)
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }")
            
            grid.addWidget(lbl_name, row, 0, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(lbl_inst, row, 1, Qt.AlignmentFlag.AlignTop)
            grid.addWidget(pbar, row, 2, Qt.AlignmentFlag.AlignTop)
            
            return pbar

        self.pb_gyro = create_sensor_row(0, "Gyroscope",
            "Leave the device completely still on a flat surface for a few seconds.")
        self.pb_accel = create_sensor_row(1, "Accelerometer",
            "Place the device in 6 different orientations (the 6 faces of a cube). "
            "Hold still for 2–3 s in each position. If stuck, tilt 45° briefly.")
        self.pb_mag = create_sensor_row(2, "Magnetometer",
            "Wave the device in the air in a figure-8 pattern.")
        self.pb_sys = create_sensor_row(3, "System",
            "Reaches 3/3 automatically once the sensors above are calibrated.")
        
        # Status log — shows offset values on save/load
        log_group = QGroupBox("Calibration Log")
        log_layout = QVBoxLayout(log_group)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setFont(QFont("Consolas", 8))
        self.log_text.setStyleSheet("background-color: #1a1a2e; color: #ddd;")
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Load Saved Calibration")
        self.btn_load.clicked.connect(self.load_requested.emit)
        
        self.btn_save = QPushButton("Save Calibration to PC")
        self.btn_save.clicked.connect(self.save_requested.emit)
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)
        main_layout.addLayout(btn_layout)
        
        self.btn_start = QPushButton("Close")
        self.btn_start.setMinimumHeight(36)
        self.btn_start.clicked.connect(self.accept)
        main_layout.addWidget(self.btn_start)

    def _log(self, msg: str):
        """Append a line to the status log."""
        self.log_text.append(msg)
        # Auto-scroll to bottom
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_bar(self, pbar: QProgressBar, val: int):
        pbar.setValue(val)
        if val == 3:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #4CAF50; }")
        elif val > 0:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #FF9800; }")
        else:
            pbar.setStyleSheet("QProgressBar::chunk { background-color: #f44336; }")

    def update_calib(self, sys_cal: int, gyro: int, accel: int, mag: int):
        self._update_bar(self.pb_sys, sys_cal)
        self._update_bar(self.pb_gyro, gyro)
        self._update_bar(self.pb_accel, accel)
        self._update_bar(self.pb_mag, mag)
        
        if sys_cal == 3 and gyro == 3 and accel == 3 and mag == 3:
            self.btn_save.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        else:
            self.btn_save.setStyleSheet("")

    def show_offsets_saved(self, offsets_str: str):
        """Called when calibration offsets are received from firmware after save."""
        parts = offsets_str.split(",")
        if len(parts) == 11:
            self._log(f"✓ Saved offsets to PC:")
            self._log(f"  Accel: [{parts[0]}, {parts[1]}, {parts[2]}]")
            self._log(f"  Gyro:  [{parts[3]}, {parts[4]}, {parts[5]}]")
            self._log(f"  Mag:   [{parts[6]}, {parts[7]}, {parts[8]}]")
            self._log(f"  Radius: accel={parts[9]}, mag={parts[10]}")
        else:
            self._log(f"✓ Saved offsets: {offsets_str}")

    def show_offsets_loaded(self, offsets_str: str):
        """Called when calibration offsets are loaded from file and sent to firmware."""
        parts = offsets_str.split(",")
        if len(parts) == 11:
            self._log(f"↻ Loaded offsets from PC → firmware:")
            self._log(f"  Accel: [{parts[0]}, {parts[1]}, {parts[2]}]")
            self._log(f"  Gyro:  [{parts[3]}, {parts[4]}, {parts[5]}]")
            self._log(f"  Mag:   [{parts[6]}, {parts[7]}, {parts[8]}]")
            self._log(f"  Radius: accel={parts[9]}, mag={parts[10]}")
        else:
            self._log(f"↻ Loaded offsets: {offsets_str}")
            
    def show_loaded_status(self):
        """When firmware confirms calibration was applied."""
        self._log("✓ Firmware confirmed: calibration offsets applied")

    def show_no_saved_calibration(self):
        """When no calibration file exists."""
        self._log("⚠ No saved calibration found on PC")

    def show_save_failed(self):
        """When save was attempted but calibration is incomplete."""
        self._log("✗ Save failed: all subsystems must be at level 3/3 first")
