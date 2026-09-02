import sys
import os
import csv
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from src.interfaces.desktop.session import create_session, resume_session, validate_csv_header, list_session_folders
from src.interfaces.desktop.constants import EIT_CSV_COLUMNS, IMU_CSV_COLUMNS_SHORT, IMU_CSV_COLUMNS_FULL, MARKER_CSV_COLUMNS

def test_create_new_session(tmp_path):
    base_dir = str(tmp_path)
    session = create_session("P01", "20231024", "V1", base_dir, "123456")
    
    assert os.path.isdir(session.folder_path)
    assert session.session_id == "P01_20231024_V1_T123456"
    assert session.eit_path.endswith("P01_20231024_V1_T123456_EIT.csv")
    assert session.is_resumed is False
    assert session.participant == "P01"
    
def test_create_session_collision_suffix(tmp_path):
    base_dir = str(tmp_path)
    # Create first session
    create_session("P01", "20231024", "V1", base_dir, "000000")
    # Create second session with same parameters
    session2 = create_session("P01", "20231024", "V1", base_dir, "000000")
    
    assert session2.session_id == "P01_20231024_V1_T000000_2"
    assert os.path.isdir(session2.folder_path)

def create_valid_csv(path, header):
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerow([0] * len(header))

def test_resume_session_valid(tmp_path):
    base_dir = str(tmp_path)
    session = create_session("P02", "20231024", "V1", base_dir, "111111")
    
    # Create valid files
    create_valid_csv(session.eit_path, EIT_CSV_COLUMNS)
    create_valid_csv(session.imu_path, IMU_CSV_COLUMNS_FULL)
    create_valid_csv(session.marker_path, MARKER_CSV_COLUMNS)
    
    resumed = resume_session(session.folder_path)
    assert resumed.is_resumed is True
    assert resumed.session_id == session.session_id

def test_resume_session_invalid_header(tmp_path):
    base_dir = str(tmp_path)
    session = create_session("P03", "20231024", "V1", base_dir, "222222")
    
    # Create invalid file
    create_valid_csv(session.eit_path, ["wrong", "header"])
    
    with pytest.raises(ValueError, match="Invalid EIT CSV header"):
        resume_session(session.folder_path)

def test_resume_session_no_files(tmp_path):
    base_dir = str(tmp_path)
    session = create_session("P04", "20231024", "V1", base_dir, "333333")
    
    with pytest.raises(ValueError, match="No valid session CSV files found"):
        resume_session(session.folder_path)

def test_resume_session_nonexistent(tmp_path):
    with pytest.raises(ValueError, match="Directory does not exist"):
        resume_session(str(tmp_path / "nonexistent"))

def test_validate_csv_header_match(tmp_path):
    csv_path = tmp_path / "test.csv"
    create_valid_csv(str(csv_path), EIT_CSV_COLUMNS)
    assert validate_csv_header(str(csv_path), EIT_CSV_COLUMNS) is True

def test_validate_csv_header_mismatch(tmp_path):
    csv_path = tmp_path / "test.csv"
    create_valid_csv(str(csv_path), EIT_CSV_COLUMNS)
    assert validate_csv_header(str(csv_path), IMU_CSV_COLUMNS_FULL) is False

def test_list_session_folders(tmp_path):
    base_dir = str(tmp_path)
    s1 = create_session("P1", "20231024", "V1", base_dir, "111")
    s2 = create_session("P2", "20231024", "V1", base_dir, "222")
    
    create_valid_csv(s1.eit_path, EIT_CSV_COLUMNS)
    create_valid_csv(s2.eit_path, EIT_CSV_COLUMNS)
    
    folders = list_session_folders(base_dir)
    assert len(folders) == 2
    assert s1.folder_path in folders
    assert s2.folder_path in folders
