import sys
import os
import csv
import queue
import pytest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from src.interfaces.desktop.writer import FileWriterThread
from src.interfaces.desktop.constants import (
    TAG_EIT, TAG_IMU, TAG_MARKER, TAG_SHUTDOWN, 
    EIT_CSV_COLUMNS, IMU_CSV_COLUMNS_FULL, MARKER_CSV_COLUMNS
)

def test_writer_creates_files_with_headers(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    # Check headers
    for path, headers in [(eit_path, EIT_CSV_COLUMNS), 
                          (imu_path, IMU_CSV_COLUMNS_FULL), 
                          (marker_path, MARKER_CSV_COLUMNS)]:
        assert os.path.exists(path)
        with open(path, 'r', newline='') as f:
            reader = csv.reader(f)
            row = next(reader)
            assert row == headers

def test_writer_writes_eit_rows(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    
    row_data = [12345, '10:00:00', 1.0, 2.0]
    q.put((TAG_EIT, row_data))
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    with open(eit_path, 'r', newline='') as f:
        reader = csv.reader(f)
        next(reader) # skip header
        row = next(reader)
        assert row == ['12345', '10:00:00', '1.0', '2.0']

def test_writer_writes_markers(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    
    row_data = ['10:00:00', 1234567890, 12345, 's', 'Session Start']
    q.put((TAG_MARKER, row_data))
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    with open(marker_path, 'r', newline='') as f:
        reader = csv.reader(f)
        next(reader) # skip header
        row = next(reader)
        assert row == ['10:00:00', '1234567890', '12345', 's', 'Session Start']

def test_writer_appends_without_duplicate_headers(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    # Pre-create EIT file with header
    with open(eit_path, 'w', newline='') as f:
        csv.writer(f).writerow(EIT_CSV_COLUMNS)
        
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    q.put((TAG_EIT, [12345, '10:00:00', 1.0, 2.0]))
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    with open(eit_path, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) == 2 # 1 header, 1 data row
        assert rows[0] == EIT_CSV_COLUMNS
        assert rows[1] == ['12345', '10:00:00', '1.0', '2.0']

def test_writer_shutdown_drains_queue(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    
    # Enqueue many rows before starting
    for i in range(100):
        q.put((TAG_EIT, [i, '10:00:00', 1.0, 2.0]))
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    with open(eit_path, 'r', newline='') as f:
        reader = csv.reader(f)
        rows = list(reader)
        assert len(rows) == 101 # 1 header + 100 data rows

def test_writer_emits_rows_written_signal(tmp_path):
    q = queue.Queue()
    eit_path = str(tmp_path / "eit.csv")
    imu_path = str(tmp_path / "imu.csv")
    marker_path = str(tmp_path / "markers.csv")
    
    writer = FileWriterThread(q, eit_path, imu_path, marker_path)
    
    from PyQt6.QtCore import Qt
    mock_slot = MagicMock()
    writer.rows_written.connect(mock_slot, Qt.ConnectionType.DirectConnection)
    
    q.put((TAG_EIT, [1, '10:00:00', 1.0, 2.0]))
    q.put((TAG_IMU, [1, '10:00:00'] + [0]*14))
    q.put((TAG_SHUTDOWN, None))
    
    writer.start()
    writer.wait()
    
    # Check that signal was emitted
    assert mock_slot.called
