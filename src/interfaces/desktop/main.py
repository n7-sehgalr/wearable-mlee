import sys
import os
import time
import datetime
import collections
import queue
import logging
import traceback

import numpy as np
import serial
import serial.tools.list_ports

# Suppress Qt DPI warning on Windows
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "0"

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QComboBox, QMessageBox, QGroupBox, QGridLayout,
                             QDialog, QCheckBox)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer, QMutex, QMutexLocker
from PyQt6.QtGui import QFont
import pyqtgraph as pg

try:
    import pyautogui
except ImportError:
    pyautogui = None

try:
    import pygetwindow as gw
except ImportError:
    gw = None

from .constants import (
    MARKER_KEYS, MARKER_COLORS,
    TAG_EIT, TAG_IMU, TAG_MARKER, TAG_SHUTDOWN,
    EIT_CSV_COLUMNS, IMU_CSV_COLUMNS_SHORT, IMU_CSV_COLUMNS_FULL,
    MARKER_CSV_COLUMNS,
    EIT_FIELD_COUNT, IMU_FIELD_COUNT_SHORT, IMU_FIELD_COUNT_FULL,
    COMBINED_FIELD_COUNT_OLD,
    SERIAL_BAUDRATE, SERIAL_QUEUE_MAXLEN, SERIAL_READ_TIMEOUT,
    RECONNECT_INTERVAL_MS, RECONNECT_MAX_ATTEMPTS,
    RENDER_FPS, RENDER_INTERVAL_MS,
    MARKER_DEDUP_INTERVAL_MS, MARKER_RECENT_LOG_SIZE,
    MARKER_FEEDBACK_DURATION_MS,
    EIT_DISPLAY_MAX_POINTS, IMU_DISPLAY_MAX_POINTS,
    EIT_SMOOTHING_METHOD, EIT_EMA_CUTOFF_HZ, EIT_MA_WINDOW_SAMPLES,
    WRITER_QUEUE_MAXSIZE, WRITER_SHUTDOWN_TIMEOUT_S,
    SESSION_TIME_FORMAT, SESSION_DATE_FORMAT,
    DEFAULT_DATA_DIR, PARTICIPANT_DB_FILENAME,
)
from .plotter import DataPlotter
from .writer import FileWriterThread
from .session import SessionInfo, create_session, resume_session
from .participant_db import ParticipantDB
from .participant_dialog import ParticipantDialog
from .calibration import StaticCalibrationDialog

# ======================================================================
# Configure logging
# ======================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ======================================================================
# Serial Worker — runs in its own thread, pushes lines into a queue
# ======================================================================
class SerialWorker(QThread):
    """Background thread that reads lines from the serial port.

    Lines are accumulated in a thread-safe deque as (wall_timestamp, line)
    tuples.  The GUI reads from the deque on a timer — this decouples
    serial I/O from rendering so the GUI never freezes.
    """
    error_occurred = pyqtSignal(str)
    connection_lost = pyqtSignal()

    def __init__(self, port, baudrate=SERIAL_BAUDRATE):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.is_running = False
        # Thread-safe line buffer (main thread drains it on a timer)
        self._lock = QMutex()
        self._line_queue = collections.deque(maxlen=SERIAL_QUEUE_MAXLEN)

    def drain_lines(self):
        """Called from the GUI thread to grab all queued lines at once.

        Returns a list of (wall_timestamp_iso, line_text) tuples.
        """
        with QMutexLocker(self._lock):
            lines = list(self._line_queue)
            self._line_queue.clear()
        return lines

    def run(self):
        try:
            self.serial_conn = serial.Serial(
                self.port, self.baudrate, timeout=SERIAL_READ_TIMEOUT
            )
            self.is_running = True
            while self.is_running:
                try:
                    if self.serial_conn.in_waiting > 0:
                        raw = self.serial_conn.readline()
                        wall_ts = datetime.datetime.now().isoformat()
                        try:
                            line = raw.decode('utf-8', errors='replace').strip()
                        except Exception:
                            continue
                        if line:
                            with QMutexLocker(self._lock):
                                self._line_queue.append((wall_ts, line))
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

    def send_command(self, cmd: str):
        """Send a command string to the serial port (for calibration etc.)."""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                self.serial_conn.write((cmd + "\n").encode('utf-8'))
                self.serial_conn.flush()
            except serial.SerialException as e:
                logger.error(f"Failed to send command '{cmd}': {e}")


# ======================================================================
# Main Window
# ======================================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wearable EIT & IMU Logger")
        self.resize(1100, 900)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # State
        self.is_recording = False
        self.serial_worker = None
        self.base_dir = DEFAULT_DATA_DIR
        os.makedirs(self.base_dir, exist_ok=True)

        # Counters
        self.eit_packet_count = 0
        self.imu_packet_count = 0
        self.skipped_line_count = 0

        # Current hardware timestamp (string) for markers
        self.last_hardware_timestamp = "0"
        self.latest_display_text = ""
        self.calib_dialog = None
        self.last_yaw = None

        # Writer thread state
        self._writer_thread = None
        self._writer_queue = None
        self._session_info = None

        # Marker deduplication
        self._last_marker_times = {}

        # Session time prefix (set when recording starts)
        self._session_time_prefix = None

        # Detected IMU format
        self._imu_field_count = IMU_FIELD_COUNT_FULL

        # Reconnection state
        self._reconnecting = False
        self._reconnect_port = None
        self._reconnect_attempts = 0
        self._was_recording_before_disconnect = False
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.timeout.connect(self._attempt_reconnect)

        # Participant DB
        db_path = os.path.join(self.base_dir, PARTICIPANT_DB_FILENAME)
        self._participant_db = ParticipantDB(db_path)

        self.init_ui()

        # ----- Render timer (~30 fps) — redraws all plots -----
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._render_tick)
        self.render_timer.start(RENDER_INTERVAL_MS)

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
            datetime.datetime.now().strftime(SESSION_DATE_FORMAT))
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

        # Row 2: OTBioLab+, Reconnect, Participant DB
        self.chk_otbiolab = QCheckBox("Sync OTBioLab+")
        self.chk_otbiolab.setToolTip(
            "When checked, pressing Record will also start recording "
            "in OTBioLab+ (requires reference button screenshots in "
            "otbiolab_assets/ folder)")
        if pyautogui is None or gw is None:
            self.chk_otbiolab.setEnabled(False)
            self.chk_otbiolab.setToolTip(
                "Requires pyautogui and pygetwindow packages")
        control_layout.addWidget(self.chk_otbiolab, 2, 0, 1, 2)

        self.btn_participants = QPushButton("📋 Participants")
        self.btn_participants.clicked.connect(self._open_participant_dialog)
        self.btn_participants.setToolTip("Open participant database")
        control_layout.addWidget(self.btn_participants, 2, 2)

        self.btn_reconnect = QPushButton("⟳ Reconnect Now")
        self.btn_reconnect.clicked.connect(self._manual_reconnect)
        self.btn_reconnect.setVisible(False)
        self.btn_reconnect.setStyleSheet(
            "QPushButton { background-color: #e67e22; color: white; "
            "font-weight: bold; padding: 4px 10px; }")
        control_layout.addWidget(self.btn_reconnect, 2, 4, 1, 2)

        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)

        # --- Marker Legend ---
        marker_group = QGroupBox("Marker Keys (press while recording)")
        marker_layout = QHBoxLayout()
        marker_group.setLayout(marker_layout)

        for key in MARKER_KEYS:
            name = MARKER_KEYS[key]
            color = MARKER_COLORS[key]
            lbl = QLabel(f"  [{key.upper()}] {name}  ")
            lbl.setStyleSheet(
                f"background-color: {color}; color: #1a1a2e; "
                f"border-radius: 4px; padding: 3px 6px; "
                f"font-weight: bold; font-size: 9pt;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marker_layout.addWidget(lbl)
        marker_layout.addStretch()

        main_layout.addWidget(marker_group)

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

        # --- Writer status row ---
        writer_row = QHBoxLayout()
        self.lbl_writer_status = QLabel("Writer: idle")
        self.lbl_writer_status.setFont(QFont("Consolas", 9))
        writer_row.addWidget(self.lbl_writer_status)
        writer_row.addStretch()
        main_layout.addLayout(writer_row)

        # --- Recent Markers log ---
        self.lbl_recent_markers = QLabel("")
        self.lbl_recent_markers.setFont(QFont("Consolas", 8))
        self.lbl_recent_markers.setStyleSheet("color: #aaa;")
        self._recent_markers = []
        main_layout.addWidget(self.lbl_recent_markers)

        # --- Plots ---
        plots_layout = QGridLayout()

        self.plot_eit1 = DataPlotter(
            "EIT Channel 1 Magnitude",
            labels=["Mag 1"], colors=[(0, 255, 255)],
            max_points=EIT_DISPLAY_MAX_POINTS,
            enable_smoothing=True,
            smoothing_method=EIT_SMOOTHING_METHOD,
            ema_cutoff_hz=EIT_EMA_CUTOFF_HZ,
            ma_window=EIT_MA_WINDOW_SAMPLES)
        self.plot_eit2 = DataPlotter(
            "EIT Channel 2 Magnitude",
            labels=["Mag 2"], colors=[(255, 0, 255)],
            max_points=EIT_DISPLAY_MAX_POINTS,
            enable_smoothing=True,
            smoothing_method=EIT_SMOOTHING_METHOD,
            ema_cutoff_hz=EIT_EMA_CUTOFF_HZ,
            ma_window=EIT_MA_WINDOW_SAMPLES)

        self.plot_imu_accel = DataPlotter(
            "IMU Linear Acceleration",
            labels=["Ax", "Ay", "Az"],
            colors=[(255, 80, 80), (80, 255, 80), (80, 120, 255)],
            max_points=IMU_DISPLAY_MAX_POINTS)
        self.plot_imu_accel.enableAutoRange(axis='y', enable=False)
        self.plot_imu_accel.setYRange(-15, 15)

        self.plot_imu_orient = DataPlotter(
            "IMU Orientation",
            labels=["Yaw", "Roll", "Pitch"],
            colors=[(255, 180, 0), (0, 220, 220), (220, 0, 220)],
            max_points=IMU_DISPLAY_MAX_POINTS)

        plots_layout.addWidget(self.plot_eit1, 0, 0)
        plots_layout.addWidget(self.plot_eit2, 1, 0)
        plots_layout.addWidget(self.plot_imu_accel, 0, 1)
        plots_layout.addWidget(self.plot_imu_orient, 1, 1)

        main_layout.addLayout(plots_layout)

        self.statusBar().showMessage(
            "Ready — Close Arduino IDE Serial Monitor before connecting")

    # ------------------------------------------------------------------
    # Render tick — called at ~30 fps
    # ------------------------------------------------------------------
    def _render_tick(self):
        """Drain the serial queue, parse every line, then redraw plots once."""
        if self.serial_worker is None or not self.serial_worker.is_running:
            return

        items = self.serial_worker.drain_lines()

        # Bound how many items we process per tick to keep GUI responsive
        MAX_ITEMS_PER_TICK = 200
        for wall_ts, line in items[:MAX_ITEMS_PER_TICK]:
            self._parse_line(line, wall_ts)

        # If we couldn't process everything, remaining items were already
        # drained from the serial deque — they must still go to the writer.
        # Enqueue them directly without display processing.
        if len(items) > MAX_ITEMS_PER_TICK:
            for wall_ts, line in items[MAX_ITEMS_PER_TICK:]:
                self._parse_line_write_only(line, wall_ts)

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
    def _parse_line(self, line, wall_ts):
        """Parse one serial line into EIT or IMU data.

        Updates display plots AND enqueues to the writer if recording.
        """
        clean_line = line.strip('\x00\r\n\t ')
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

        if clean_line.startswith("# CALIBRATION:"):
            # Firmware calibration load status
            if self.calib_dialog and self.calib_dialog.isVisible():
                if "Loaded" in clean_line:
                    self.calib_dialog.show_loaded_status()
            self.statusBar().showMessage(clean_line)
            return

        if clean_line.startswith("# CALIBRATION SAVED"):
            self.statusBar().showMessage("✓ Calibration saved to EEPROM")
            return

        if clean_line.startswith("# CALIBRATION LOADED"):
            self.statusBar().showMessage("✓ Calibration loaded from EEPROM")
            if self.calib_dialog and self.calib_dialog.isVisible():
                self.calib_dialog.show_loaded_status()
            return

        # Skip firmware comment / status lines
        if not clean_line or clean_line[0] == '#':
            self.skipped_line_count += 1
            return

        parts = clean_line.split(',')
        nfields = len(parts)

        # ---- EIT packet (3 columns) ----
        if nfields == EIT_FIELD_COUNT:
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

            if self.is_recording and self._writer_queue is not None:
                row = [parts[0].strip(), wall_ts,
                       parts[1].strip(), parts[2].strip()]
                try:
                    self._writer_queue.put_nowait((TAG_EIT, row))
                except queue.Full:
                    logger.warning("Writer queue full — EIT row dropped")

        # ---- IMU packet (7 or 16 columns) ----
        elif nfields in (IMU_FIELD_COUNT_SHORT, IMU_FIELD_COUNT_FULL):
            try:
                ts = float(parts[0])
                vals = [float(p) for p in parts[1:]]
            except ValueError:
                self.skipped_line_count += 1
                return

            self.imu_packet_count += 1
            self._imu_field_count = nfields
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

            # vals[0:3] = orientation, vals[3:6] = linear accel
            self.plot_imu_orient.append_sample(t, vals[0:3])
            self.plot_imu_accel.append_sample(t, vals[3:6])

            if self.is_recording and self._writer_queue is not None:
                row = [parts[0].strip(), wall_ts] + [p.strip() for p in parts[1:]]
                try:
                    self._writer_queue.put_nowait((TAG_IMU, row))
                except queue.Full:
                    logger.warning("Writer queue full — IMU row dropped")

        # ---- Old combined format (9 columns) ----
        elif nfields == COMBINED_FIELD_COUNT_OLD:
            try:
                ts = float(parts[0])
                mag1 = float(parts[1])
                mag2 = float(parts[2])
                vals = [float(p) for p in parts[3:]]
            except ValueError:
                self.skipped_line_count += 1
                return

            self.eit_packet_count += 1
            self.imu_packet_count += 1
            self.last_hardware_timestamp = parts[0].strip()
            t = ts / 1_000_000.0

            # Yaw unwrapping
            raw_yaw = vals[0]
            if self.last_yaw is not None:
                diff = raw_yaw - (self.last_yaw % 360)
                if diff > 180:
                    diff -= 360
                elif diff < -180:
                    diff += 360
                vals[0] = self.last_yaw + diff
            self.last_yaw = vals[0]

            self.plot_eit1.append_sample(t, [mag1])
            self.plot_eit2.append_sample(t, [mag2])
            self.plot_imu_orient.append_sample(t, vals[0:3])
            self.plot_imu_accel.append_sample(t, vals[3:6])

            if self.is_recording and self._writer_queue is not None:
                eit_row = [parts[0].strip(), wall_ts,
                           parts[1].strip(), parts[2].strip()]
                imu_row = [parts[0].strip(), wall_ts] + [p.strip() for p in parts[3:]]
                try:
                    self._writer_queue.put_nowait((TAG_EIT, eit_row))
                    self._writer_queue.put_nowait((TAG_IMU, imu_row))
                except queue.Full:
                    logger.warning("Writer queue full — combined row dropped")
        else:
            self.skipped_line_count += 1

    # ------------------------------------------------------------------
    def _parse_line_write_only(self, line, wall_ts):
        """Parse a line and enqueue to writer only (no display update).

        Used when the GUI render tick has too many items to process.
        """
        if not self.is_recording or self._writer_queue is None:
            return

        clean_line = line.strip('\x00\r\n\t ')
        if not clean_line or clean_line[0] == '#':
            return

        parts = clean_line.split(',')
        nfields = len(parts)

        try:
            if nfields == EIT_FIELD_COUNT:
                float(parts[0])  # validate
                row = [parts[0].strip(), wall_ts,
                       parts[1].strip(), parts[2].strip()]
                self._writer_queue.put_nowait((TAG_EIT, row))
                self.eit_packet_count += 1
                self.last_hardware_timestamp = parts[0].strip()

            elif nfields in (IMU_FIELD_COUNT_SHORT, IMU_FIELD_COUNT_FULL):
                float(parts[0])
                row = [parts[0].strip(), wall_ts] + [p.strip() for p in parts[1:]]
                self._writer_queue.put_nowait((TAG_IMU, row))
                self.imu_packet_count += 1
                self.last_hardware_timestamp = parts[0].strip()

            elif nfields == COMBINED_FIELD_COUNT_OLD:
                float(parts[0])
                eit_row = [parts[0].strip(), wall_ts,
                           parts[1].strip(), parts[2].strip()]
                imu_row = [parts[0].strip(), wall_ts] + [p.strip() for p in parts[3:]]
                self._writer_queue.put_nowait((TAG_EIT, eit_row))
                self._writer_queue.put_nowait((TAG_IMU, imu_row))
                self.eit_packet_count += 1
                self.imu_packet_count += 1
                self.last_hardware_timestamp = parts[0].strip()
        except (ValueError, queue.Full):
            pass

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
        # Handle "Cancel Reconnect" click
        if self._reconnecting:
            self._reconnect_timer.stop()
            self._reconnecting = False
            self.btn_connect.setText("Connect")
            self.btn_reconnect.setVisible(False)
            self.btn_record.setEnabled(False)
            self.statusBar().showMessage("Reconnection cancelled")
            return

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
            self.calib_dialog = StaticCalibrationDialog(self)
            self.calib_dialog.save_requested.connect(
                lambda: self.serial_worker.send_command("calibrate save"))
            self.calib_dialog.load_requested.connect(
                lambda: self.serial_worker.send_command("calibrate load"))
            self.calib_dialog.show()
        else:
            self.serial_worker.stop()
            self.serial_worker = None
            self.btn_connect.setText("Connect")
            self.btn_record.setEnabled(False)
            self.statusBar().showMessage("Disconnected")

    def toggle_recording(self):
        if not self.is_recording:
            # Start recording — create session and writer
            if self._session_info is None:
                participant = self.part_input.text().strip()
                date_str = self.date_input.text().strip()
                visit = self.visit_input.text().strip()

                if not participant or not date_str or not visit:
                    QMessageBox.warning(
                        self, "Error",
                        "Please fill in Participant, Date, and Visit.")
                    return

                time_prefix = datetime.datetime.now().strftime(SESSION_TIME_FORMAT)
                self._session_time_prefix = time_prefix

                try:
                    self._session_info = create_session(
                        participant, date_str, visit,
                        self.base_dir, time_prefix)
                except Exception as e:
                    QMessageBox.critical(self, "Session Error", str(e))
                    return

                # Record session in participant DB
                try:
                    # Ensure participant exists
                    if not self._participant_db.get_participant(participant):
                        self._participant_db.add_participant(participant)
                    self._participant_db.add_session_record(
                        participant, date_str, visit,
                        self._session_info.session_id)
                except Exception as e:
                    logger.warning(f"Failed to record session in DB: {e}")

                # Determine IMU columns
                if self._imu_field_count == IMU_FIELD_COUNT_SHORT:
                    imu_cols = IMU_CSV_COLUMNS_SHORT
                else:
                    imu_cols = IMU_CSV_COLUMNS_FULL

                # Create writer thread
                self._writer_queue = queue.Queue(maxsize=WRITER_QUEUE_MAXSIZE)
                self._writer_thread = FileWriterThread(
                    self._writer_queue,
                    self._session_info.eit_path,
                    self._session_info.imu_path,
                    self._session_info.marker_path,
                    imu_columns=imu_cols)
                self._writer_thread.writer_error.connect(self._on_writer_error)
                self._writer_thread.queue_warning.connect(self._on_queue_warning)
                self._writer_thread.session_saved.connect(self._on_session_saved)
                self._writer_thread.rows_written.connect(self._on_rows_written)
                self._writer_thread.start()

                # Trigger OTBioLab+ on new session start
                if self.chk_otbiolab.isChecked():
                    self._try_otbiolab_record()

            self.is_recording = True
            self.btn_record.setText("Pause")
            self.btn_save.setEnabled(True)
            self.statusBar().showMessage(
                f"Recording to {self._session_info.folder_path}")
        else:
            self.is_recording = False
            self.btn_record.setText("Record")
            self.statusBar().showMessage("Paused (data on disk is safe)")
        self.setFocus()

    def handle_serial_error(self, err):
        QMessageBox.critical(self, "Serial Error", err)
        if self.serial_worker:
            self.serial_worker.stop()
            self.serial_worker = None
        self.btn_connect.setText("Connect")
        self.btn_record.setEnabled(False)
        self.statusBar().showMessage("Connection failed")

    # ------------------------------------------------------------------
    # Connection-lost handling and auto-reconnection
    # ------------------------------------------------------------------
    def handle_connection_lost(self):
        """Called when the serial connection drops unexpectedly.

        The writer thread keeps files open — reconnection resumes writing.
        """
        was_recording = self.is_recording
        if self.is_recording:
            self.is_recording = False
            self.btn_record.setText("Record")

        if self.serial_worker:
            self._reconnect_port = self.serial_worker.port
            self.serial_worker.stop()
            self.serial_worker = None

        self._reconnecting = True
        self._reconnect_attempts = 0
        self._was_recording_before_disconnect = was_recording

        self.btn_connect.setText("Cancel Reconnect")
        self.btn_record.setEnabled(False)
        self.btn_reconnect.setVisible(True)

        self.statusBar().showMessage(
            f"⚠ CONNECTION LOST — Auto-reconnecting to "
            f"{self._reconnect_port}... (session preserved on disk)")

        self._reconnect_timer.start(RECONNECT_INTERVAL_MS)

    def _attempt_reconnect(self):
        self._reconnect_attempts += 1

        try:
            test_conn = serial.Serial(
                self._reconnect_port, SERIAL_BAUDRATE, timeout=0.1)
            test_conn.close()
            time.sleep(0.1)

            self._reconnect_timer.stop()
            self._reconnecting = False

            self.serial_worker = SerialWorker(self._reconnect_port)
            self.serial_worker.error_occurred.connect(
                self.handle_serial_error)
            self.serial_worker.connection_lost.connect(
                self.handle_connection_lost)
            self.serial_worker.start()

            self.btn_connect.setText("Disconnect")
            self.btn_record.setEnabled(True)
            self.btn_reconnect.setVisible(False)

            if self._was_recording_before_disconnect:
                self.is_recording = True
                self.btn_record.setText("Pause")
                self.btn_save.setEnabled(True)
                self.statusBar().showMessage(
                    f"✓ Reconnected to {self._reconnect_port} "
                    f"— Recording resumed")
            else:
                self.statusBar().showMessage(
                    f"✓ Reconnected to {self._reconnect_port}")

        except (serial.SerialException, OSError):
            self.statusBar().showMessage(
                f"⚠ Reconnecting to {self._reconnect_port}... "
                f"(attempt {self._reconnect_attempts}/{RECONNECT_MAX_ATTEMPTS})")

            if self._reconnect_attempts >= RECONNECT_MAX_ATTEMPTS:
                self._reconnect_timer.stop()
                self._reconnecting = False
                self.btn_connect.setText("Connect")
                self.statusBar().showMessage(
                    "✗ Auto-reconnect failed. "
                    "Click 'Reconnect Now' or select a port and Connect.")

    def _manual_reconnect(self):
        if self._reconnect_timer.isActive():
            self._reconnect_timer.stop()

        self._reconnect_attempts = 0
        self._reconnecting = True
        self.btn_connect.setText("Cancel Reconnect")

        self._attempt_reconnect()
        if self._reconnecting:
            self._reconnect_timer.start(RECONNECT_INTERVAL_MS)

    # ------------------------------------------------------------------
    # Writer callbacks
    # ------------------------------------------------------------------
    def _on_writer_error(self, msg):
        logger.error(f"Writer error: {msg}")
        QMessageBox.critical(self, "Writer Error",
                             f"File writer encountered an error:\n{msg}")
        self.lbl_writer_status.setText(f"Writer: ERROR — {msg}")
        self.lbl_writer_status.setStyleSheet("color: red;")

    def _on_queue_warning(self, qsize):
        logger.warning(f"Writer queue at {qsize}/{WRITER_QUEUE_MAXSIZE}")
        self.lbl_writer_status.setText(
            f"Writer: ⚠ queue {qsize}/{WRITER_QUEUE_MAXSIZE}")
        self.lbl_writer_status.setStyleSheet("color: orange;")

    def _on_session_saved(self, folder_path):
        self.lbl_writer_status.setText("Writer: idle")
        self.lbl_writer_status.setStyleSheet("")

    def _on_rows_written(self, eit, imu, markers):
        self.lbl_writer_status.setText(
            f"Writer: EIT={eit} IMU={imu} M={markers}")

    # ------------------------------------------------------------------
    # Participant database
    # ------------------------------------------------------------------
    def _open_participant_dialog(self):
        dialog = ParticipantDialog(self._participant_db, self)
        dialog.participant_selected.connect(self._on_participant_selected)
        dialog.session_resumed.connect(self._on_session_resume_requested)
        dialog.exec()

    def _on_participant_selected(self, p_id, name, visit):
        self.part_input.setText(p_id)
        self.visit_input.setText(visit)
        self.statusBar().showMessage(f"Participant: {p_id} — {name}")

    def _on_session_resume_requested(self, folder_name):
        folder_path = os.path.join(self.base_dir, folder_name)
        try:
            info = resume_session(folder_path)
            self._session_info = info
            self.part_input.setText(info.participant)
            self.date_input.setText(info.date_str)
            self.visit_input.setText(info.visit)
            self.statusBar().showMessage(
                f"Session resumed: {info.session_id}")

            # Determine IMU columns from existing file
            if self._imu_field_count == IMU_FIELD_COUNT_SHORT:
                imu_cols = IMU_CSV_COLUMNS_SHORT
            else:
                imu_cols = IMU_CSV_COLUMNS_FULL

            self._writer_queue = queue.Queue(maxsize=WRITER_QUEUE_MAXSIZE)
            self._writer_thread = FileWriterThread(
                self._writer_queue,
                info.eit_path, info.imu_path, info.marker_path,
                imu_columns=imu_cols)
            self._writer_thread.writer_error.connect(self._on_writer_error)
            self._writer_thread.queue_warning.connect(self._on_queue_warning)
            self._writer_thread.session_saved.connect(self._on_session_saved)
            self._writer_thread.rows_written.connect(self._on_rows_written)
            self._writer_thread.start()

            self.btn_save.setEnabled(True)

        except ValueError as e:
            QMessageBox.warning(self, "Resume Error", str(e))

    # ------------------------------------------------------------------
    # OTBioLab+ integration
    # ------------------------------------------------------------------
    def _try_otbiolab_record(self):
        if pyautogui is None or gw is None:
            self.statusBar().showMessage(
                "⚠ pyautogui/pygetwindow not installed — "
                "OTBioLab+ sync skipped")
            return

        assets_dir = os.path.join(
            os.path.dirname(__file__), "otbiolab_assets")
        record_img = os.path.join(assets_dir, "record_button.png")
        play_img = os.path.join(assets_dir, "play_button.png")

        if not os.path.exists(record_img):
            self.statusBar().showMessage(
                "⚠ record_button.png not found in otbiolab_assets/ — "
                "add a screenshot of the Record button")
            return

        try:
            otb_windows = gw.getWindowsWithTitle("OTBioLab+")
            if not otb_windows:
                self.statusBar().showMessage(
                    "⚠ OTBioLab+ window not found")
                return

            otb_win = otb_windows[0]
            otb_win.activate()
            time.sleep(0.5)

            record_loc = self._locate_image(record_img)

            if record_loc is None and os.path.exists(play_img):
                play_loc = self._locate_image(play_img)
                if play_loc:
                    pyautogui.click(pyautogui.center(play_loc))
                    time.sleep(1.0)
                    record_loc = self._locate_image(record_img)

            if record_loc:
                pyautogui.click(pyautogui.center(record_loc))
                time.sleep(0.3)
                self.statusBar().showMessage(
                    "✓ OTBioLab+ recording started")
            else:
                self.statusBar().showMessage(
                    "⚠ Could not locate Record button in OTBioLab+")

            self.activateWindow()
            self.raise_()

        except Exception as e:
            self.statusBar().showMessage(
                f"⚠ OTBioLab+ sync error: {e}")
            self.activateWindow()
            self.raise_()

    @staticmethod
    def _locate_image(img_path):
        if pyautogui is None or not os.path.exists(img_path):
            return None
        try:
            return pyautogui.locateOnScreen(img_path, confidence=0.8)
        except (NotImplementedError, TypeError):
            try:
                return pyautogui.locateOnScreen(img_path)
            except Exception:
                return None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Keyboard markers
    # ------------------------------------------------------------------
    def keyPressEvent(self, event):
        # Guard against auto-repeat
        if event.isAutoRepeat():
            super().keyPressEvent(event)
            return

        key = event.text().lower()
        if key in MARKER_KEYS and self.is_recording:
            # Deduplication
            now_ms = time.time() * 1000
            last = self._last_marker_times.get(key, 0)
            if now_ms - last < MARKER_DEDUP_INTERVAL_MS:
                super().keyPressEvent(event)
                return
            self._last_marker_times[key] = now_ms

            wall_ts = datetime.datetime.now().isoformat()
            epoch_ts = time.time()
            event_name = MARKER_KEYS[key]
            hw_ts = self.last_hardware_timestamp

            # Enqueue to writer immediately
            if self._writer_queue is not None:
                marker_row = [wall_ts, epoch_ts, hw_ts, key, event_name]
                try:
                    self._writer_queue.put_nowait((TAG_MARKER, marker_row))
                except queue.Full:
                    logger.warning("Writer queue full — marker dropped!")

            # Visual feedback on EIT plots
            t = float(hw_ts) / 1_000_000.0 if hw_ts != "0" else 0.0
            color = MARKER_COLORS.get(key, '#FFFFFF')
            self.plot_eit1.add_marker(t, key, event_name, color)
            self.plot_eit2.add_marker(t, key, event_name, color)

            # Recent markers log
            self._recent_markers.append(
                f"[{key.upper()}] {event_name} @ {wall_ts[-12:]}")
            if len(self._recent_markers) > MARKER_RECENT_LOG_SIZE:
                self._recent_markers.pop(0)
            self.lbl_recent_markers.setText(
                "Recent markers: " + " | ".join(self._recent_markers))

            # Status bar confirmation
            self.statusBar().showMessage(
                f"✓ Marker recorded: [{key.upper()}] {event_name}")

        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Save & Stop
    # ------------------------------------------------------------------
    def save_data(self):
        if self.is_recording:
            self.is_recording = False
            self.btn_record.setText("Record")

        if self._writer_queue is not None and self._writer_thread is not None:
            # Signal shutdown and wait for drain
            try:
                self._writer_queue.put(
                    (TAG_SHUTDOWN, None), timeout=WRITER_SHUTDOWN_TIMEOUT_S)
            except queue.Full:
                logger.error("Could not send shutdown to writer — queue full")

            self._writer_thread.wait(
                int(WRITER_SHUTDOWN_TIMEOUT_S * 1000))

            folder = self._session_info.folder_path if self._session_info else "unknown"
            QMessageBox.information(
                self, "Session Saved",
                f"Data saved to:\n{folder}")

            self._writer_thread = None
            self._writer_queue = None

        self._session_info = None
        self._session_time_prefix = None
        self.btn_save.setEnabled(False)
        self.lbl_writer_status.setText("Writer: idle")

    # ------------------------------------------------------------------
    # Close confirmation
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        has_active_session = self._writer_thread is not None

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Confirm Exit")
        msg_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.No)

        if has_active_session:
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText("An active recording session exists!")
            msg_box.setInformativeText(
                "Data has been continuously saved to disk. "
                "Closing will flush and finalize the session files.\n\n"
                "Close the application?")
        else:
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setText(
                "Are you sure you want to close the application?")

        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            # Flush writer if active
            if self._writer_queue is not None and self._writer_thread is not None:
                try:
                    self._writer_queue.put_nowait((TAG_SHUTDOWN, None))
                except queue.Full:
                    pass
                self._writer_thread.wait(
                    int(WRITER_SHUTDOWN_TIMEOUT_S * 1000))

            # Clean up timers and serial
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
            if self.serial_worker and self.serial_worker.is_running:
                self.serial_worker.stop()

            # Close participant DB
            try:
                self._participant_db.close()
            except Exception:
                pass

            event.accept()
        else:
            event.ignore()


# ======================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    pg.setConfigOptions(antialias=True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
