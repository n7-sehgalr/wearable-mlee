import csv
import os
import time
import queue
import logging
from PyQt6.QtCore import QThread, pyqtSignal

from .constants import (
    TAG_EIT, TAG_IMU, TAG_MARKER, TAG_SHUTDOWN,
    EIT_CSV_COLUMNS, IMU_CSV_COLUMNS_SHORT, IMU_CSV_COLUMNS_FULL,
    MARKER_CSV_COLUMNS,
    WRITER_BATCH_INTERVAL_S, WRITER_FSYNC_INTERVAL_S,
    WRITER_QUEUE_MAXSIZE, WRITER_QUEUE_WARN_THRESHOLD,
)

logger = logging.getLogger(__name__)


class FileWriterThread(QThread):
    """Background thread that writes EIT, IMU, and marker data to CSV files.
    
    Design:
    - Consumes tagged tuples from a shared queue.Queue(maxsize=WRITER_QUEUE_MAXSIZE)
    - Queue protocol: (tag, row_data) where tag is TAG_EIT/TAG_IMU/TAG_MARKER/TAG_SHUTDOWN
    - Opens 3 CSV files using csv.writer (NOT pandas)
    - Writes headers only if file is new or empty
    - Appends rows in batches every ~WRITER_BATCH_INTERVAL_S seconds
    - Calls file.flush() after each batch
    - Calls os.fsync() every ~WRITER_FSYNC_INTERVAL_S seconds
    - On TAG_SHUTDOWN: drains remaining queue, flushes, fsyncs, closes all files
    - On exception: emits writer_error signal with error message, logs full traceback
    - Never silently discards data
    - If queue gets >80% full, emits queue_warning signal
    """
    
    writer_error = pyqtSignal(str)       # error message for GUI
    queue_warning = pyqtSignal(int)      # current queue size when warning
    session_saved = pyqtSignal(str)      # session folder path on clean shutdown
    rows_written = pyqtSignal(int, int, int)  # (eit_count, imu_count, marker_count)
    
    def __init__(self, data_queue: queue.Queue,
                 eit_path: str, imu_path: str, marker_path: str,
                 imu_columns: list[str] | None = None):
        """Initialize the writer.
        
        Parameters:
            data_queue: bounded queue.Queue shared with GUI thread
            eit_path: full path to EIT CSV file
            imu_path: full path to IMU CSV file  
            marker_path: full path to markers CSV file
            imu_columns: column list for IMU CSV (auto-detect if None;
                         defaults to IMU_CSV_COLUMNS_FULL)
        """
        super().__init__()
        self._queue = data_queue
        self._eit_path = eit_path
        self._imu_path = imu_path
        self._marker_path = marker_path
        self._imu_columns = imu_columns or IMU_CSV_COLUMNS_FULL
        self._running = False
        self._eit_count = 0
        self._imu_count = 0
        self._marker_count = 0
    
    def run(self):
        """Main writer loop."""
        logger.info(f"Session started, opening files in: {os.path.dirname(self._eit_path)}")
        self._running = True
        
        # File handles and writers
        eit_fh = None
        imu_fh = None
        marker_fh = None
        
        try:
            # Open files and write headers if empty
            eit_fh, eit_writer = self._open_csv(self._eit_path, EIT_CSV_COLUMNS)
            imu_fh, imu_writer = self._open_csv(self._imu_path, self._imu_columns)
            marker_fh, marker_writer = self._open_csv(self._marker_path, MARKER_CSV_COLUMNS)
            
            last_fsync_time = time.time()
            
            # Batch buffers
            eit_batch = []
            imu_batch = []
            marker_batch = []
            
            def _flush_batches():
                if eit_batch:
                    eit_writer.writerows(eit_batch)
                    self._eit_count += len(eit_batch)
                    eit_batch.clear()
                if imu_batch:
                    imu_writer.writerows(imu_batch)
                    self._imu_count += len(imu_batch)
                    imu_batch.clear()
                if marker_batch:
                    marker_writer.writerows(marker_batch)
                    self._marker_count += len(marker_batch)
                    marker_batch.clear()
                
                # Flush to OS buffers
                eit_fh.flush()
                imu_fh.flush()
                marker_fh.flush()
            
            shutdown_requested = False
            
            while self._running or shutdown_requested:
                try:
                    # Attempt to get an item from the queue
                    # When this times out, we flush the current batches
                    item = self._queue.get(timeout=WRITER_BATCH_INTERVAL_S)
                    
                    tag, data = item
                    
                    if tag == TAG_EIT:
                        eit_batch.append(data)
                    elif tag == TAG_IMU:
                        imu_batch.append(data)
                    elif tag == TAG_MARKER:
                        marker_batch.append(data)
                    elif tag == TAG_SHUTDOWN:
                        shutdown_requested = True
                        self._running = False
                    else:
                        logger.warning(f"Unknown queue tag received: {tag}")
                    
                    self._queue.task_done()
                    
                except queue.Empty:
                    # Timeout reached, proceed to flush batches
                    pass
                
                # If shutdown requested, keep looping until queue is empty to drain it
                if shutdown_requested and not self._queue.empty():
                    continue
                
                # Flush batches to disk
                _flush_batches()
                
                # Emit rows written for UI updates
                self.rows_written.emit(self._eit_count, self._imu_count, self._marker_count)
                
                # Check for fsync
                current_time = time.time()
                if current_time - last_fsync_time >= WRITER_FSYNC_INTERVAL_S:
                    self._fsync_file(eit_fh)
                    self._fsync_file(imu_fh)
                    self._fsync_file(marker_fh)
                    last_fsync_time = current_time
                    
                # Warn if queue is getting too full
                qsize = self._queue.qsize()
                if qsize > WRITER_QUEUE_MAXSIZE * WRITER_QUEUE_WARN_THRESHOLD:
                    self.queue_warning.emit(qsize)
                    
                # If shutdown was requested and queue is drained, exit loop
                if shutdown_requested and self._queue.empty():
                    break
            
            # Final fsync before closing
            self._fsync_file(eit_fh)
            self._fsync_file(imu_fh)
            self._fsync_file(marker_fh)
            
            logger.info(f"Session closed successfully. Rows written: EIT={self._eit_count}, IMU={self._imu_count}, Markers={self._marker_count}")
            session_dir = os.path.dirname(self._eit_path)
            self.session_saved.emit(session_dir)
            
        except Exception as e:
            logger.error(f"Writer thread encountered an error: {e}", exc_info=True)
            self.writer_error.emit(str(e))
        finally:
            if eit_fh:
                try:
                    eit_fh.close()
                except Exception:
                    pass
            if imu_fh:
                try:
                    imu_fh.close()
                except Exception:
                    pass
            if marker_fh:
                try:
                    marker_fh.close()
                except Exception:
                    pass

    def _open_csv(self, path: str, columns: list[str]) -> tuple:
        """Open a CSV file for appending. Write header if empty.
        Returns (file_handle, csv_writer)."""
        file_exists = os.path.exists(path)
        is_empty = not file_exists or os.path.getsize(path) == 0
        
        # open with newline='' as recommended for csv module
        fh = open(path, 'a', newline='', encoding='utf-8')
        writer = csv.writer(fh)
        
        if is_empty:
            writer.writerow(columns)
            fh.flush()
            
        return fh, writer

    def _fsync_file(self, fh) -> None:
        """Flush and fsync a file handle."""
        if fh and not fh.closed:
            try:
                fh.flush()
                os.fsync(fh.fileno())
            except OSError as e:
                logger.warning(f"Failed to fsync file {fh.name}: {e}")

    @property
    def total_rows_written(self) -> int:
        return self._eit_count + self._imu_count + self._marker_count
