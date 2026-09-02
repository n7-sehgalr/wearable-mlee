import os
import csv
import logging
from dataclasses import dataclass
from typing import List, Optional

from .constants import (
    EIT_CSV_COLUMNS,
    IMU_CSV_COLUMNS_SHORT,
    IMU_CSV_COLUMNS_FULL,
    MARKER_CSV_COLUMNS
)

logger = logging.getLogger(__name__)

@dataclass
class SessionInfo:
    folder_path: str
    eit_path: str
    imu_path: str
    marker_path: str
    is_resumed: bool
    participant: str
    date_str: str
    visit: str
    session_id: str

def create_session(participant: str, date_str: str, visit: str, base_dir: str, time_prefix: str) -> SessionInfo:
    """Create a new session directory and return SessionInfo."""
    base_session_id = f"{participant}_{date_str}_{visit}_T{time_prefix}"
    session_id = base_session_id
    folder_path = os.path.join(base_dir, session_id)
    
    counter = 2
    while os.path.exists(folder_path):
        session_id = f"{base_session_id}_{counter}"
        folder_path = os.path.join(base_dir, session_id)
        counter += 1
        
    os.makedirs(folder_path)
    logger.info(f"Created new session folder: {folder_path}")
    
    return SessionInfo(
        folder_path=folder_path,
        eit_path=os.path.join(folder_path, f"{session_id}_EIT.csv"),
        imu_path=os.path.join(folder_path, f"{session_id}_IMU.csv"),
        marker_path=os.path.join(folder_path, f"{session_id}_markers.csv"),
        is_resumed=False,
        participant=participant,
        date_str=date_str,
        visit=visit,
        session_id=session_id
    )

def validate_csv_header(filepath: str, expected_columns: List[str]) -> bool:
    """Check if the first line of a CSV matches expected columns."""
    try:
        with open(filepath, 'r', newline='') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if header is None:
                return False
            # Allow for optional carriage returns or spaces
            return [h.strip() for h in header] == expected_columns
    except Exception as e:
        logger.error(f"Error validating CSV header in {filepath}: {e}")
        return False

def resume_session(folder_path: str) -> SessionInfo:
    """Resume an existing session by validating CSV schemas."""
    if not os.path.isdir(folder_path):
        raise ValueError(f"Directory does not exist: {folder_path}")
        
    session_id = os.path.basename(folder_path)
    parts = session_id.split('_')
    
    if len(parts) < 4:
        raise ValueError(f"Invalid session folder name format: {session_id}")
        
    participant = parts[0]
    date_str = parts[1]
    visit = parts[2]
    
    # Look for CSV files matching the session_id pattern
    eit_path = os.path.join(folder_path, f"{session_id}_EIT.csv")
    imu_path = os.path.join(folder_path, f"{session_id}_IMU.csv")
    marker_path = os.path.join(folder_path, f"{session_id}_markers.csv")
    
    # Also check for files with any prefix ending in _EIT.csv etc. (fallback)
    if not os.path.exists(eit_path):
        for f in os.listdir(folder_path):
            if f.endswith('_EIT.csv'):
                eit_path = os.path.join(folder_path, f)
                break
    if not os.path.exists(imu_path):
        for f in os.listdir(folder_path):
            if f.endswith('_IMU.csv'):
                imu_path = os.path.join(folder_path, f)
                break
    if not os.path.exists(marker_path):
        for f in os.listdir(folder_path):
            if f.endswith('_markers.csv'):
                marker_path = os.path.join(folder_path, f)
                break
    
    has_valid_csv = False
    
    if os.path.exists(eit_path):
        if not validate_csv_header(eit_path, EIT_CSV_COLUMNS):
            raise ValueError("Invalid EIT CSV header")
        has_valid_csv = True
        
    if os.path.exists(imu_path):
        is_short = validate_csv_header(imu_path, IMU_CSV_COLUMNS_SHORT)
        is_full = validate_csv_header(imu_path, IMU_CSV_COLUMNS_FULL)
        if not (is_short or is_full):
            raise ValueError("Invalid IMU CSV header")
        has_valid_csv = True
        
    if os.path.exists(marker_path):
        if not validate_csv_header(marker_path, MARKER_CSV_COLUMNS):
            raise ValueError("Invalid Marker CSV header")
        has_valid_csv = True
        
    if not has_valid_csv:
        raise ValueError("No valid session CSV files found to resume.")
        
    return SessionInfo(
        folder_path=folder_path,
        eit_path=eit_path,
        imu_path=imu_path,
        marker_path=marker_path,
        is_resumed=True,
        participant=participant,
        date_str=date_str,
        visit=visit,
        session_id=session_id
    )

def list_session_folders(base_dir: str) -> List[str]:
    """List all valid session folders in the data directory, sorted by most recent first."""
    if not os.path.exists(base_dir):
        return []
        
    valid_folders = []
    for d in os.listdir(base_dir):
        folder_path = os.path.join(base_dir, d)
        if os.path.isdir(folder_path):
            try:
                # Try to validate via resume_session, if it works, it's valid
                resume_session(folder_path)
                valid_folders.append(folder_path)
            except ValueError:
                pass
                
    # Sort by modification time, newest first
    valid_folders.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return valid_folders
