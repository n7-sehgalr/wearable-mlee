import sys
import os
import time
import datetime
import collections
import numpy as np
import pandas as pd
import serial
import serial.tools.list_ports

# Suppress Qt DPI warning on Windows
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QComboBox, QMessageBox, QGroupBox, QGridLayout, QDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QMutex, QMutexLocker
from PyQt6.QtGui import QFont
import pyqtgraph as pg

try:
    import pyautogui
except ImportError:
    pass  # PyAutoGUI is optional


# ======================================================================
# Serial Worker — runs in its own thread, pushes lines into a queue
# ======================================================================
class SerialWorker(QThread):
    """Background thread that reads lines from the serial port.

    Lines are accumulated in a thread-safe deque.  The GUI reads
    from the deque on a timer — this decouples serial I/O from
    rendering so the GUI never freezes.
    """
    error_occurred = pyqtSignal(str)
    connection_lost = pyqtSignal()

    def __init__(self, port, baudrate=115200):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        # Thread-safe line buffer (main thread drains it on a timer)
        self._lock = QMutex()
        self._line_queue = collections.deque(maxlen=5000)

    def drain_lines(self):
        """Called from the GUI thread to grab all queued lines at once."""
        with QMutexLocker(self._lock):
            lines = list(self._line_queue)
            self._line_queue.clear()
        return lines

    def run(self):
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=0.05
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
                            with QMutexLocker(self._lock):
                                self._line_queue.append(line)
                    else:
                        self.msleep(1)
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


# ======================================================================
# Plot Widget — only stores data; redraws are triggered externally
# ======================================================================
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
        self.enableAutoRange(axis='y')
        self.enableAutoRange(axis='x', enable=False)
        self.setXRange(0, max_points, padding=0)

        if labels is None:
            labels = ["Data"]
        if colors is None:
            colors = [(255, 0, 0)]

        self.labels = labels
        self.data_buffers = {label: np.zeros(max_points) for label in labels}
        self.ptr = 0  # total samples received (clamped to max_points)
        self._dirty = False  # whether new data arrived since last redraw

        for i, label in enumerate(labels):
            color = colors[i % len(colors)]
            curve = self.plot(pen=pg.mkPen(color=color, width=2), name=label)
            self.curves.append((label, curve))

    def append_sample(self, t, values):
        """Append one sample to the ring buffer (cheap, no redraw)."""
        for i, (label, _curve) in enumerate(self.curves):
            self.data_buffers[label][:-1] = self.data_buffers[label][1:]
            self.data_buffers[label][-1] = values[i]

        if self.ptr < self.max_points:
            self.ptr += 1
        self._dirty = True

    def redraw(self):
        """Redraw curves from ring buffer.  Called from the GUI timer."""
        if not self._dirty:
            return
        self._dirty = False

        # Only show the portion of the buffer that has real data
        start = max(0, self.max_points - self.ptr)

        for label, curve in self.curves:
            y = self.data_buffers[label][start:]
            # Plot against static X axis (indices) to eliminate pyqtgraph autoscaling jitter
            curve.setData(y)


# ======================================================================
# Calibration Dialog
# ======================================================================
class CalibrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("IMU Calibration")
        self.resize(350, 200)
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
        
        self.btn_start = QPushButton("Start Session (Bypass)")
        self.btn_start.clicked.connect(self.accept)
        layout.addWidget(self.btn_start)
        
    def update_calib(self, sys_cal, gyro, accel, mag):
        self.lbl_sys.setText(f"System: {sys_cal}/3")
        self.lbl_gyro.setText(f"Gyroscope: {gyro}/3")
        self.lbl_accel.setText(f"Accelerometer: {accel}/3")
        self.lbl_mag.setText(f"Magnetometer: {mag}/3")
        if sys_cal == 3 and gyro == 3 and accel == 3 and mag == 3:
            self.btn_start.setText("Start Session (Fully Calibrated)")
            self.btn_start.setStyleSheet("background-color: green; color: white;")


# ======================================================================
# Main Window
# ======================================================================
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
            os.path.join(os.path.dirname(__file__),
                         "..", "..", "..", "data", "01_raw")
        )

        # Counters
        self.eit_packet_count = 0
        self.imu_packet_count = 0
        self.skipped_line_count = 0

        # Buffers for saving
        self.eit_data = []
        self.imu_data = []
        self.markers = []
        self.last_hardware_timestamp = "0"
        self.latest_display_text = ""
        self.calib_dialog = None
        self.last_yaw = None

        self.init_ui()

        # ----- Render timer (30 fps) — redraws all four plots -----
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._render_tick)
        self.render_timer.start(33)  # ~30 fps

    # ------------------------------------------------------------------
    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Control Panel ---
        control_group = QGroupBox("Session Details")
        control_layout = QGridLayout()

        self.part_input = QLineEdit("P01")
        self.date_input = QLineEdit(
            datetime.datetime.now().strftime("%Y%m%d"))
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
        self.lbl_calib_status = QLabel("Calib[Sys:0 G:0 A:0 M:0]")
        self.lbl_last_line = QLabel("Last line: (none)")
        self.lbl_last_line.setMaximumWidth(600)
        for lbl in (self.lbl_eit_count, self.lbl_imu_count,
                     self.lbl_skipped, self.lbl_calib_status):
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
            labels=["Mag 1"], colors=[(0, 255, 255)])
        self.plot_eit2 = DataPlotter(
            "EIT Channel 2 Magnitude",
            labels=["Mag 2"], colors=[(255, 0, 255)])
            
        self.plot_imu_accel = DataPlotter(
            "IMU Linear Acceleration",
            labels=["Ax", "Ay", "Az"],
            colors=[(255, 80, 80), (80, 255, 80), (80, 120, 255)])
        self.plot_imu_accel.enableAutoRange(axis='y', enable=False)
        self.plot_imu_accel.setYRange(-15, 15)
        
        self.plot_imu_orient = DataPlotter(
            "IMU Orientation",
            labels=["Yaw", "Roll", "Pitch"],
            colors=[(255, 180, 0), (0, 220, 220), (220, 0, 220)])
        self.plot_imu_orient.enableAutoRange(axis='y', enable=True)

        plots_layout.addWidget(self.plot_eit1, 0, 0)
        plots_layout.addWidget(self.plot_eit2, 1, 0)
        plots_layout.addWidget(self.plot_imu_accel, 0, 1)
        plots_layout.addWidget(self.plot_imu_orient, 1, 1)

        main_layout.addLayout(plots_layout)

        self.statusBar().showMessage(
            "Ready — Close Arduino IDE Serial Monitor before connecting")

    # ------------------------------------------------------------------
    # Render tick — called at 30 fps
    # ------------------------------------------------------------------
    def _render_tick(self):
        """Drain the serial queue, parse every line, then redraw plots once."""
        if self.serial_worker is None or not self.serial_worker.is_running:
            return

        lines = self.serial_worker.drain_lines()
        for line in lines:
            self._parse_line(line)

        # Single batch-redraw of all four plots
        self.plot_eit1.redraw()
        self.plot_eit2.redraw()
        self.plot_imu_accel.redraw()
        self.plot_imu_orient.redraw()

        # Update status labels
        self.lbl_eit_count.setText(f"EIT: {self.eit_packet_count} pkts")
        self.lbl_imu_count.setText(f"IMU: {self.imu_packet_count} pkts")
        self.lbl_skipped.setText(f"Skipped: {self.skipped_line_count}")
        if self.latest_display_text:
            self.lbl_last_line.setText(f"Last: {self.latest_display_text}")
            self.latest_display_text = ""

    # ------------------------------------------------------------------
    def _parse_line(self, line):
        """Parse one serial line into EIT or IMU data."""
        # Strip all invisible characters to ensure exact matching
        clean_line = line.strip('\x00\r\n\t ')
        
        # Debug display (last line) - save text but don't update UI label directly
        self.latest_display_text = clean_line if len(clean_line) <= 80 else clean_line[:77] + "..."

        if clean_line.startswith("# CALIB:"):
            parts = clean_line.replace("# CALIB:", "").strip().split(",")
            if len(parts) == 4:
                try:
                    s, g, a, m = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                    self.lbl_calib_status.setText(f"Calib[Sys:{s} G:{g} A:{a} M:{m}]")
                    if self.calib_dialog and self.calib_dialog.isVisible():
                        self.calib_dialog.update_calib(s, g, a, m)
                except ValueError:
                    pass
            return

        # Skip firmware comment / status lines
        if not clean_line or clean_line[0] == '#':
            self.skipped_line_count += 1
            return

        parts = clean_line.split(',')
        nfields = len(parts)

        # ---- EIT packet (3 columns) ----
        if nfields == 3:
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
            self.plot_eit1.append_sample(t, [mag1])
            self.plot_eit2.append_sample(t, [mag2])

            if self.is_recording:
                self.eit_data.append([p.strip() for p in parts])

        # ---- IMU packet (7 columns) ----
        elif nfields == 7:
            try:
                ts = float(parts[0])
                vals = [float(p) for p in parts[1:]]
            except ValueError:
                self.skipped_line_count += 1
                return

            self.imu_packet_count += 1
            self.last_hardware_timestamp = parts[0].strip()
            t = ts / 1_000_000.0
            
            # Continuous Unwrapping for Yaw to prevent 360->0 jumps
            raw_yaw = vals[0]
            if self.last_yaw is not None:
                diff = raw_yaw - (self.last_yaw % 360)
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                vals[0] = self.last_yaw + diff
            self.last_yaw = vals[0]
                
            # vals = [rx, ry, rz, ax, ay, az]
            self.plot_imu_orient.append_sample(t, vals[0:3])
            self.plot_imu_accel.append_sample(t, vals[3:6])

            if self.is_recording:
                self.imu_data.append([p.strip() for p in parts])

        # ---- Old combined format (9 columns: ts,m1,m2,rx,ry,rz,ax,ay,az) ----
        elif nfields == 9:
            try:
                ts = float(parts[0])
                mag1 = float(parts[1])
                mag2 = float(parts[2])
                vals = [float(p) for p in parts[3:]]
            except ValueError:
                self.skipped_line_count += 1
                return

            # Treat as both EIT + IMU
            self.eit_packet_count += 1
            self.imu_packet_count += 1
            self.last_hardware_timestamp = parts[0].strip()
            t = ts / 1_000_000.0
            
            # Continuous Unwrapping for Yaw to prevent 360->0 jumps
            raw_yaw = vals[3]  # in 9-col format, yaw is index 3
            if self.last_yaw is not None:
                diff = raw_yaw - (self.last_yaw % 360)
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                vals[3] = self.last_yaw + diff
            self.last_yaw = vals[3]
                
            self.plot_eit1.append_sample(t, [mag1])
            self.plot_eit2.append_sample(t, [mag2])
            self.plot_imu_orient.append_sample(t, vals[0:3])
            self.plot_imu_accel.append_sample(t, vals[3:6])

            if self.is_recording:
                self.eit_data.append([
                    parts[0].strip(), parts[1].strip(), parts[2].strip()
                ])
                self.imu_data.append([
                    parts[0].strip()] + [p.strip() for p in parts[3:]])

        else:
            self.skipped_line_count += 1

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def refresh_ports(self):
        self.port_combo.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_combo.addItem(
                f"{p.device}  ({p.description})", p.device)

    def toggle_connection(self):
        if self.serial_worker is None or not self.serial_worker.is_running:
            idx = self.port_combo.currentIndex()
            if idx < 0:
                QMessageBox.warning(self, "Error", "No COM port selected.")
                return
            port = self.port_combo.itemData(idx)

            self.eit_packet_count = 0
            self.imu_packet_count = 0
            self.skipped_line_count = 0

            self.serial_worker = SerialWorker(port)
            self.serial_worker.error_occurred.connect(
                self.handle_serial_error)
            self.serial_worker.connection_lost.connect(
                self.handle_connection_lost)
            self.serial_worker.start()

            self.btn_connect.setText("Disconnect")
            self.btn_record.setEnabled(True)
            self.statusBar().showMessage(f"Connected to {port}")
            self.setFocus()
            
            # Show calibration dialog
            self.calib_dialog = CalibrationDialog(self)
            self.calib_dialog.show()
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
                self, "Error",
                "Please fill in Participant, Date, and Visit.")
            return

        prefix = f"{participant}_{date_str}_{visit}"
        target_dir = os.path.join(self.base_dir, prefix)
        os.makedirs(target_dir, exist_ok=True)

        saved = []

        if self.eit_data:
            df = pd.DataFrame(
                self.eit_data, columns=['timestamp_us', 'mag1', 'mag2'])
            path = os.path.join(target_dir, f"{prefix}_EIT.csv")
            df.to_csv(path, index=False)
            saved.append(f"EIT ({len(self.eit_data)} rows)")

        if self.imu_data:
            df = pd.DataFrame(
                self.imu_data,
                columns=['timestamp_us', 'rx_yaw', 'ry_roll', 'rz_pitch',
                         'ax', 'ay', 'az'])
            path = os.path.join(target_dir, f"{prefix}_IMU.csv")
            df.to_csv(path, index=False)
            saved.append(f"IMU ({len(self.imu_data)} rows)")

        if self.markers:
            df = pd.DataFrame(
                self.markers,
                columns=['sys_timestamp', 'hardware_timestamp_us',
                         'key', 'event'])
            path = os.path.join(target_dir, f"{prefix}_markers.csv")
            df.to_csv(path, index=False)
            saved.append(f"Markers ({len(self.markers)} rows)")

        if saved:
            QMessageBox.information(
                self, "Success",
                f"Saved to:\n{target_dir}\n\n" + "\n".join(saved))
        else:
            QMessageBox.warning(
                self, "Nothing to save", "No data was recorded.")

        self.eit_data.clear()
        self.imu_data.clear()
        self.markers.clear()
        self.btn_save.setEnabled(False)

    def closeEvent(self, event):
        if self.serial_worker and self.serial_worker.is_running:
            self.serial_worker.stop()
        event.accept()


# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
