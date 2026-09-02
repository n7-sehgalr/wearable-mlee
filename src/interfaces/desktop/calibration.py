from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt, pyqtSignal

class StaticCalibrationDialog(QDialog):
    """Dialog for static BNO055 calibration with EEPROM persistence.
    
    Flow:
    1. Shows current calibration levels (updated externally via update_calib())
    2. 'Save Calibration' button: emits save_requested signal
       (parent sends 'calibrate save' to firmware)
    3. 'Load Calibration' button: emits load_requested signal
       (parent sends 'calibrate load' to firmware)
    4. 'Start Session' button: accepts dialog
    """
    
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IMU Calibration")
        self.resize(350, 250)
        
        layout = QVBoxLayout(self)
        
        self.lbl_info = QLabel(
            "<b>IMU Calibration Required</b><br><br>"
            "1. <b>Gyroscope:</b> Leave the device resting completely still on a flat surface.<br>"
            "2. <b>Magnetometer:</b> Move the device in a figure-8 motion."
        )
        self.lbl_info.setWordWrap(True)
        layout.addWidget(self.lbl_info)
        
        self.lbl_sys = QLabel("System: 0/3")
        self.lbl_gyro = QLabel("Gyroscope: 0/3")
        self.lbl_accel = QLabel("Accelerometer: 0/3")
        self.lbl_mag = QLabel("Magnetometer: 0/3")
        
        layout.addWidget(self.lbl_sys)
        layout.addWidget(self.lbl_gyro)
        layout.addWidget(self.lbl_accel)
        layout.addWidget(self.lbl_mag)
        
        btn_layout = QHBoxLayout()
        
        self.btn_load = QPushButton("Load Calibration")
        self.btn_load.clicked.connect(self.load_requested.emit)
        
        self.btn_save = QPushButton("Save Calibration")
        self.btn_save.clicked.connect(self.save_requested.emit)
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)
        
        self.btn_start = QPushButton("Start Session (Bypass)")
        self.btn_start.clicked.connect(self.accept)
        layout.addWidget(self.btn_start)

    def update_calib(self, sys_cal: int, gyro: int, accel: int, mag: int):
        self.lbl_sys.setText(f"System: {sys_cal}/3")
        self.lbl_gyro.setText(f"Gyroscope: {gyro}/3")
        self.lbl_accel.setText(f"Accelerometer: {accel}/3")
        self.lbl_mag.setText(f"Magnetometer: {mag}/3")
        
        if sys_cal == 3 and gyro == 3 and accel == 3 and mag == 3:
            self.btn_start.setText("Start Session (Fully Calibrated)")
            self.btn_start.setStyleSheet("background-color: green; color: white;")
        
    def show_loaded_status(self):
        """When calibration is loaded from EEPROM, show blue status."""
        self.btn_start.setText("Start Session (Calib Loaded)")
        self.btn_start.setStyleSheet("background-color: blue; color: white;")
