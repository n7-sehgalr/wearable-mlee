"""Shared constants for the Wearable EIT & IMU Logger.

All marker definitions, CSV column schemas, filter parameters, writer
configuration, and session-naming conventions live here so that every
module imports from a single source of truth.
"""

import os

# ======================================================================
# Marker definitions — shared between legend UI, key handler, and writer
# ======================================================================
MARKER_KEYS = {
    'e': 'EMG Start',
    'i': 'EIT Start',
    'c': 'COSMED Start',
    's': 'Session Start',
    'x': 'Session End',
    'l': 'Blood Lactate Sample',
    'o': 'Other',
}

MARKER_COLORS = {
    'e': '#FF6B6B',
    'i': '#4ECDC4',
    'c': '#45B7D1',
    's': '#96CEB4',
    'x': '#FFEAA7',
    'l': '#DDA0DD',
    'o': '#B0BEC5',
}

# ======================================================================
# CSV column schemas
# ======================================================================
EIT_CSV_COLUMNS = ['timestamp_us', 'wall_timestamp', 'mag1', 'mag2']

# Old 7-column IMU (orientation + linear accel only)
IMU_CSV_COLUMNS_SHORT = [
    'timestamp_us', 'wall_timestamp',
    'rx_yaw', 'ry_roll', 'rz_pitch',
    'ax', 'ay', 'az',
]

# New 16-column IMU (+ gyro + gravity + quaternion)
IMU_CSV_COLUMNS_FULL = [
    'timestamp_us', 'wall_timestamp',
    'rx_yaw', 'ry_roll', 'rz_pitch',
    'ax', 'ay', 'az',
    'gx', 'gy', 'gz',
    'gravx', 'gravy', 'gravz',
    'qw', 'qx', 'qy', 'qz',
]

MARKER_CSV_COLUMNS = [
    'wall_timestamp', 'wall_timestamp_epoch',
    'hardware_timestamp_us', 'key', 'event',
]

# ======================================================================
# Writer queue message tags
# ======================================================================
TAG_EIT = "eit"
TAG_IMU = "imu"
TAG_MARKER = "marker"
TAG_SHUTDOWN = "shutdown"

# ======================================================================
# Writer configuration
# ======================================================================
WRITER_QUEUE_MAXSIZE = 50_000          # bounded queue capacity
WRITER_BATCH_INTERVAL_S = 1.0         # seconds between batch writes
WRITER_FSYNC_INTERVAL_S = 5.0         # seconds between os.fsync() calls
WRITER_SHUTDOWN_TIMEOUT_S = 5.0       # max wait for writer drain on shutdown
WRITER_QUEUE_WARN_THRESHOLD = 0.80    # warn when queue is 80% full

# ======================================================================
# EIT display / filter parameters
# ======================================================================
EIT_SMOOTHING_METHOD = "ema"           # "ema" or "ma"
EIT_EMA_CUTOFF_HZ = 0.8               # EMA low-pass cutoff
EIT_MA_WINDOW_SAMPLES = 400           # rolling MA window size
EIT_DISPLAY_WINDOW_SECONDS = 30       # visible scrolling time window (seconds)
EIT_DISPLAY_MAX_POINTS = 2000         # ring buffer size for display
EIT_AUTOSCALE_PADDING = 0.10          # 10% Y padding
EIT_AUTOSCALE_MIN_RANGE = 0.005       # minimum Y range to prevent jitter
EIT_AUTOSCALE_HYSTERESIS = 0.05       # only update range when it changes by >5%
EIT_RAW_CURVE_ALPHA = 80              # alpha (0-255) for raw signal overlay

# IMU display
IMU_DISPLAY_MAX_POINTS = 1000         # ring buffer size for IMU plots

# ======================================================================
# Serial / acquisition
# ======================================================================
SERIAL_BAUDRATE = 115200
SERIAL_QUEUE_MAXLEN = 5000            # serial worker deque maxlen
SERIAL_READ_TIMEOUT = 0.05            # serial read timeout (seconds)

# Reconnection
RECONNECT_INTERVAL_MS = 2000          # ms between reconnection attempts
RECONNECT_MAX_ATTEMPTS = 30

# Render timer
RENDER_FPS = 30
RENDER_INTERVAL_MS = 33               # ~30 fps

# ======================================================================
# Marker display
# ======================================================================
MARKER_DEDUP_INTERVAL_MS = 500        # ignore repeated keys within this window
MARKER_MAX_VISIBLE_ANNOTATIONS = 50   # max annotations on plot
MARKER_RECENT_LOG_SIZE = 5            # recent marker log entries shown
MARKER_FEEDBACK_DURATION_MS = 2000    # how long marker flash lasts

# ======================================================================
# Session naming
# ======================================================================
SESSION_TIME_FORMAT = "%H%M%S"
SESSION_DATE_FORMAT = "%Y%m%d"

# ======================================================================
# Data directories
# ======================================================================
DEFAULT_DATA_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__),
                 "..", "..", "..", "data", "01_raw")
)

# Participant database
PARTICIPANT_DB_FILENAME = "participants.db"

# ======================================================================
# Firmware packet field counts (for auto-detection)
# ======================================================================
EIT_FIELD_COUNT = 3                    # timestamp, mag1, mag2
IMU_FIELD_COUNT_SHORT = 7              # timestamp + 6 vals (old firmware)
IMU_FIELD_COUNT_FULL = 17              # timestamp + 16 vals (new firmware)
COMBINED_FIELD_COUNT_OLD = 9           # legacy combined format
