import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..')))

from src.interfaces.desktop.participant_db import ParticipantDB

def test_create_and_get_participant(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001", "John Doe", "Test notes")
    p = db.get_participant("P001")
    
    assert p is not None
    assert p["id"] == "P001"
    assert p["name"] == "John Doe"
    assert p["notes"] == "Test notes"
    
    db.close()

def test_duplicate_participant_raises(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001", "John Doe")
    with pytest.raises(ValueError, match="already exists"):
        db.add_participant("P001", "Jane Doe")
        
    db.close()

def test_list_participants_with_search(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001", "Alice")
    db.add_participant("P002", "Bob")
    
    all_p = db.list_participants()
    assert len(all_p) == 2
    
    search_p = db.list_participants(search="Alice")
    assert len(search_p) == 1
    assert search_p[0]["id"] == "P001"
    
    db.close()

def test_update_participant(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001", "Alice", "Old notes")
    db.update_participant("P001", name="Alice Smith", notes="New notes")
    
    p = db.get_participant("P001")
    assert p["name"] == "Alice Smith"
    assert p["notes"] == "New notes"
    
    db.close()

def test_add_and_get_session(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001")
    db.add_session_record("P001", "20231024", "V1", "/fake/folder")
    
    sessions = db.get_sessions_for_participant("P001")
    assert len(sessions) == 1
    assert sessions[0]["visit"] == "V1"
    assert sessions[0]["folder"] == "/fake/folder"
    
    db.close()

def test_sessions_ordered_by_date(tmp_path):
    import time
    db_path = str(tmp_path / "test.db")
    db = ParticipantDB(db_path)
    
    db.add_participant("P001")
    db.add_session_record("P001", "20231024", "V1", "/fake/1")
    time.sleep(0.01) # Ensure different created_at
    db.add_session_record("P001", "20231025", "V2", "/fake/2")
    
    sessions = db.get_sessions_for_participant("P001")
    assert len(sessions) == 2
    # Should be newest first by created_at
    assert sessions[0]["visit"] == "V2"
    assert sessions[1]["visit"] == "V1"
    
    db.close()
