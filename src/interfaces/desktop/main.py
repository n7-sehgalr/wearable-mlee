import sys
import os
import time
import datetime
import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports

# Suppress Qt DPI warning on Windows
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QComboBox, QMessageBox, QGroupBox, QGridLayout,
                             QStatusBar)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont
import pyqtgraph as pg

try:
    import pyautogui
except ImportError:
    pass  # PyAutoGUI is optional


class SerialWorker(QThread):
    """Background thread that reads lines from the serial port."""
    data_received = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    connection_lost = pyqtSignal()

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False

    def run(self):
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=0.1
            )
            self.is_running = True
            while self.is_running:
                try:
                    if self.serial_conn.in_waiting > 0:
                        raw = self.serial_conn.readline()
                        try:
                            line = raw.decode('utf-8', errors='replace').strip()
                        except Exception:
                            continue
                        if line:
                            self.data_received.emit(line)
                    else:
                        self.msleep(1)  # Prevent busy-spin when no data
                except serial.SerialException:
                    self.connection_lost.emit()
                    break
        except serial.SerialException as e:
            self.error_occurred.emit(
                f"Cannot open {self.port}.\n\n"
                f"Make sure the Arduino IDE Serial Monitor is CLOSED — "
                f"only one application can use a COM port at a time.\n\n"
                f"Details: {e}"
            )
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.is_running = False

    def stop(self):
        self.is_running = False
        self.wait(2000)


class DataPlotter(pg.PlotWidget):
    """Real-time scrolling plot with optional moving-average smoothing."""

    def __init__(self, title, labels=None, colors=None, max_points=500):
        super().__init__()
        self.setTitle(title, color='w', size='10pt')
        self.showGrid(x=True, y=True, alpha=0.3)
        self.addLegend(offset=(10, 10))
        self.setLabel('bottom', 'Time', units='s')
        self.max_points = max_points
        self.curves = []

        if labels is None:
            labels = ["Data"]
        if colors is None:
            colors = [(255, 0, 0)]

        self.data_buffers = {label: np.zeros(max_points) for label in labels}
        self.time_buffer = np.zeros(max_points)
        self.ptr = 0

        for i, label in enumerate(labels):
            color = colors[i % len(colors)]
            curve = self.plot(pen=pg.mkPen(color=color, width=2), name=label)
            self.curves.append((label, curve))

    def update_data(self, t, values, smooth_window=5):
        """Shift buffers left, append new sample, redraw."""
        self.time_buffer[:-1] = self.time_buffer[1:]
        self.time_buffer[-1] = t

        for i, (label, curve) in enumerate(self.curves):
            self.data_buffers[label][:-1] = self.data_buffers[label][1:]
            self.data_buffers[label][-1] = values[i]

            if self.ptr >= smooth_window:
                kernel = np.ones(smooth_window) / smooth_window
                smoothed = np.convolve(
                    self.data_buffers[label], kernel, mode='same'
                )
                curve.setData(self.time_buffer, smoothed)
            else:
                curve.setData(self.time_buffer, self.data_buffers[label])

        if self.ptr < self.max_points:
            self.ptr += 1


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wearable EIT & IMU Logger")
        self.resize(1100, 850)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # State
        self.is_recording = False
        self.serial_worker = None
        self.base_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "01_raw")
        )

        # Counters for status display
        self.eit_packet_count = 0
        self.imu_packet_count = 0
        self.skipped_line_count = 0

        # Buffers for saving
        self.eit_data = []
        self.imu_data = []
        self.markers = []
        self.last_hardware_timestamp = "0"

        self.init_ui()

        # Periodic status update timer (every 500 ms)
        self.status_timer = QTimer(self)
        self.status_timer.timeout.connect(self.update_status_counts)
        self.status_timer.start(500)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Control Panel ---
        control_group = QGroupBox("Session Details")
        control_layout = QGridLayout()

        self.part_input = QLineEdit("P01")
        self.date_input = QLineEdit(datetime.datetime.now().strftime("%Y%m%d"))
        self.visit_input = QLineEdit("V1")

        control_layout.addWidget(QLabel("Participant ID:"), 0, 0)
        control_layout.addWidget(self.part_input, 0, 1)
        control_layout.addWidget(QLabel("Date:"), 0, 2)
        control_layout.addWidget(self.date_input, 0, 3)
        control_layout.addWidget(QLabel("Visit:"), 0, 4)
        control_layout.addWidget(self.visit_input, 0, 5)

        self.port_combo = QComboBox()
        self.refresh_ports()

        self.btn_refresh = QPushButton("Refresh Ports")
        self.btn_refresh.clicked.connect(self.refresh_ports)

        self.btn_connect = QPushButton("Connect")
        self.btn_connect.clicked.connect(self.toggle_connection)

        self.btn_record = QPushButton("Record")
        self.btn_record.clicked.connect(self.toggle_recording)
        self.btn_record.setEnabled(False)

        self.btn_save = QPushButton("Save && Stop")
        self.btn_save.clicked.connect(self.save_data)
        self.btn_save.setEnabled(False)

        control_layout.addWidget(QLabel("COM Port:"), 1, 0)
        control_layout.addWidget(self.port_combo, 1, 1)
        control_layout.addWidget(self.btn_refresh, 1, 2)
        control_layout.addWidget(self.btn_connect, 1, 3)
        control_layout.addWidget(self.btn_record, 1, 4)
        control_layout.addWidget(self.btn_save, 1, 5)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # --- Status indicators ---
        status_row = QHBoxLayout()
        self.lbl_eit_count = QLabel("EIT: 0 pkts")
        self.lbl_imu_count = QLabel("IMU: 0 pkts")
        self.lbl_skipped = QLabel("Skipped: 0")
        self.lbl_last_line = QLabel("Last line: (none)")
        self.lbl_last_line.setMaximumWidth(600)
        for lbl in (self.lbl_eit_count, self.lbl_imu_count, self.lbl_skipped):
            lbl.setFont(QFont("Consolas", 9))
            status_row.addWidget(lbl)
        self.lbl_last_line.setFont(QFont("Consolas", 8))
        status_row.addWidget(self.lbl_last_line)
        status_row.addStretch()
        main_layout.addLayout(status_row)

        # --- Plots ---
        plots_layout = QGridLayout()

        self.plot_eit1 = DataPlotter(
            "EIT Channel 1 Magnitude",
            labels=["Mag 1"], colors=[(0, 255, 255)]
        )
        self.plot_eit2 = DataPlotter(
            "EIT Channel 2 Magnitude",
            labels=["Mag 2"], colors=[(255, 0, 255)]
        )
        self.plot_imu_accel = DataPlotter(
            "IMU Linear Acceleration",
            labels=["Ax", "Ay", "Az"],
            colors=[(255, 80, 80), (80, 255, 80), (80, 120, 255)]
        )
        self.plot_imu_orient = DataPlotter(
            "IMU Orientation",
            labels=["Yaw", "Roll", "Pitch"],
            colors=[(255, 180, 0), (0, 220, 220), (220, 0, 220)]
        )

        plots_layout.addWidget(self.plot_eit1, 0, 0)
        plots_layout.addWidget(self.plot_eit2, 1, 0)
        plots_layout.addWidget(self.plot_imu_accel, 0, 1)
        plots_layout.addWidget(self.plot_imu_orient, 1, 1)

        main_layout.addLayout(plots_layout)

        # Status Bar
        self.statusBar().showMessage("Ready  —  Close Arduino IDE Serial Monitor before connecting")

    def update_status_counts(self):
        """Periodically refresh the packet-count labels."""
        self.lbl_eit_count.setText(f"EIT: {self.eit_packet_count} pkts")
        self.lbl_imu_count.setText(f"IMU: {self.imu_packet_count} pkts")
        self.lbl_skipped.setText(f"Skipped: {self.skipped_line_count}")

    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(f"{p.device}  ({p.description})", p.device)

    def toggle_connection(self):
        if self.serial_worker is None or not self.serial_worker.is_running:
            idx = self.port_combo.currentIndex()
            if idx < 0:
                QMessageBox.warning(self, "Error", "No COM port selected.")
                return
            port = self.port_combo.itemData(idx)

            # Reset counters
            self.eit_packet_count = 0
            self.imu_packet_count = 0
            self.skipped_line_count = 0

            self.serial_worker = SerialWorker(port)
            self.serial_worker.data_received.connect(self.handle_serial_data)
            self.serial_worker.error_occurred.connect(self.handle_serial_error)
            self.serial_worker.connection_lost.connect(self.handle_connection_lost)
            self.serial_worker.start()

            self.btn_connect.setText("Disconnect")
            self.btn_record.setEnabled(True)
            self.statusBar().showMessage(f"Connected to {port}")
            self.setFocus()
        else:
            self.serial_worker.stop()
            self.serial_worker = None
            self.btn_connect.setText("Connect")
            self.btn_record.setEnabled(False)
            self.statusBar().showMessage("Disconnected")

    def toggle_recording(self):
        if not self.is_recording:
            self.is_recording = True
            self.btn_record.setText("Pause")
            self.btn_save.setEnabled(True)
            self.statusBar().showMessage("Recording...")
        else:
            self.is_recording = False
            self.btn_record.setText("Record")
            self.statusBar().showMessage("Paused")
        self.setFocus()

    # ------------------------------------------------------------------
    # Serial data parsing
    # ------------------------------------------------------------------
    def handle_serial_data(self, line):
        """Parse an incoming serial line.
        
        We differentiate packets purely by the number of comma-separated
        numeric fields:
          EIT  → 3 fields: timestamp_us, mag1, mag2
          IMU  → 7 fields: timestamp_us, rx, ry, rz, ax, ay, az
        
        Lines that start with '#' are firmware status messages and are
        silently skipped.  Any other non-numeric line is counted as
        'skipped' so the user can see if the firmware format is wrong.
        """
        # Update debug display
        display = line if len(line) <= 80 else line[:77] + "..."
        self.lbl_last_line.setText(f"Last: {display}")

        # Skip firmware comment / status lines
        if line.startswith('#') or line.startswith('\r'):
            self.skipped_line_count += 1
            return

        parts = line.split(',')

        # ---- EIT packet (3 columns) ----
        if len(parts) == 3:
            try:
                ts = float(parts[0])
                mag1 = float(parts[1])
                mag2 = float(parts[2])
            except ValueError:
                self.skipped_line_count += 1
                return

            self.eit_packet_count += 1
            self.last_hardware_timestamp = parts[0].strip()
            t = ts / 1_000_000.0
            self.plot_eit1.update_data(t, [mag1])
            self.plot_eit2.update_data(t, [mag2])

            if self.is_recording:
                self.eit_data.append([
                    parts[0].strip(), parts[1].strip(), parts[2].strip()
                ])

        # ---- IMU packet (7 columns) ----
        elif len(parts) == 7:
            try:
                ts = float(parts[0])
                rx = float(parts[1])
                ry = float(parts[2])
                rz = float(parts[3])
                ax = float(parts[4])
                ay = float(parts[5])
                az = float(parts[6])
            except ValueError:
                self.skipped_line_count += 1
                return

            self.imu_packet_count += 1
            self.last_hardware_timestamp = parts[0].strip()
            t = ts / 1_000_000.0
            self.plot_imu_orient.update_data(t, [rx, ry, rz])
            self.plot_imu_accel.update_data(t, [ax, ay, az])

            if self.is_recording:
                self.imu_data.append([p.strip() for p in parts])

        else:
            self.skipped_line_count += 1

    def handle_serial_error(self, err):
        QMessageBox.critical(self, "Serial Error", err)
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker = None
        self.btn_connect.setText("Connect")
        self.btn_record.setEnabled(False)
        self.statusBar().showMessage("Connection failed")

    def handle_connection_lost(self):
        self.statusBar().showMessage("Serial connection lost!")
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker = None
        self.btn_connect.setText("Connect")
        self.btn_record.setEnabled(False)

    # ------------------------------------------------------------------
    # Keyboard markers
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        key = event.text().lower()
        valid_keys = {
            'l': 'Lactate',
            'e': 'Electrode',
            's': 'Session Start',
            'o': 'Other',
        }

        if key in valid_keys and self.is_recording:
            timestamp = time.time()
            event_name = valid_keys[key]
            self.markers.append([
                timestamp, self.last_hardware_timestamp, key, event_name
            ])
            self.statusBar().showMessage(f"✓ Marker: {event_name}")

            # Optional: Mirror keypress to OT Biolab
            # if 'pyautogui' in sys.modules:
            #     pyautogui.press(key)

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def save_data(self):
        if self.is_recording:
            self.toggle_recording()

        participant = self.part_input.text().strip()
        date_str = self.date_input.text().strip()
        visit = self.visit_input.text().strip()

        if not participant or not date_str or not visit:
            QMessageBox.warning(
                self, "Error", "Please fill in Participant, Date, and Visit."
            )
            return

        prefix = f"{participant}_{date_str}_{visit}"
        target_dir = os.path.join(self.base_dir, prefix)
        os.makedirs(target_dir, exist_ok=True)

        saved = []

        if self.eit_data:
            df = pd.DataFrame(
                self.eit_data, columns=['timestamp_us', 'mag1', 'mag2']
            )
            path = os.path.join(target_dir, f"{prefix}_EIT.csv")
            df.to_csv(path, index=False)
            saved.append(f"EIT ({len(self.eit_data)} rows)")

        if self.imu_data:
            df = pd.DataFrame(
                self.imu_data,
                columns=[
                    'timestamp_us', 'rx_yaw', 'ry_roll', 'rz_pitch',
                    'ax', 'ay', 'az',
                ],
            )
            path = os.path.join(target_dir, f"{prefix}_IMU.csv")
            df.to_csv(path, index=False)
            saved.append(f"IMU ({len(self.imu_data)} rows)")

        if self.markers:
            df = pd.DataFrame(
                self.markers,
                columns=[
                    'sys_timestamp', 'hardware_timestamp_us', 'key', 'event'
                ],
            )
            path = os.path.join(target_dir, f"{prefix}_markers.csv")
            df.to_csv(path, index=False)
            saved.append(f"Markers ({len(self.markers)} rows)")

        if saved:
            QMessageBox.information(
                self, "Success",
                f"Saved to:\n{target_dir}\n\n" + "\n".join(saved)
            )
        else:
            QMessageBox.warning(self, "Nothing to save", "No data was recorded.")

        self.eit_data.clear()
        self.imu_data.clear()
        self.markers.clear()
        self.btn_save.setEnabled(False)

    def closeEvent(self, event):
        """Clean up serial thread on window close."""
        if self.serial_worker and self.serial_worker.is_running:
            self.serial_worker.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Dark theme for pyqtgraph
    pg.setConfigOptions(antialias=True)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
