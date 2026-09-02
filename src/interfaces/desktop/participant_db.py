import sqlite3
import logging
import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

class ParticipantDB:
    """Lightweight SQLite database for participant and session management."""
    
    def __init__(self, db_path: str):
        """Open or create the database at db_path."""
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._enable_wal()
        self.create_tables()
        
    def _enable_wal(self):
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to enable WAL mode: {e}")
            
    def create_tables(self):
        """Create tables if they don't exist."""
        try:
            with self.conn:
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS participants (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        notes TEXT,
                        created_at TEXT
                    )
                ''')
                
                self.conn.execute('''
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        participant_id TEXT NOT NULL,
                        date TEXT NOT NULL,
                        visit TEXT NOT NULL, 
                        folder TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY(participant_id) REFERENCES participants(id)
                    )
                ''')
        except sqlite3.Error as e:
            logger.error(f"Failed to create tables: {e}")
            
    def add_participant(self, participant_id: str, name: str = '', notes: str = '') -> None:
        """Add a new participant. Raises if ID already exists."""
        created_at = datetime.datetime.now().isoformat()
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO participants (id, name, notes, created_at) VALUES (?, ?, ?, ?)",
                    (participant_id, name, notes, created_at)
                )
        except sqlite3.IntegrityError:
            raise ValueError(f"Participant with ID {participant_id} already exists.")
            
    def get_participant(self, participant_id: str) -> Optional[Dict[str, Any]]:
        """Get participant by ID. Returns dict with id, name, notes, created_at."""
        cursor = self.conn.execute("SELECT * FROM participants WHERE id = ?", (participant_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
        
    def list_participants(self, search: str = '') -> List[Dict[str, Any]]:
        """List all participants, optionally filtered by search string."""
        if search:
            cursor = self.conn.execute(
                "SELECT * FROM participants WHERE id LIKE ? OR name LIKE ? ORDER BY created_at DESC",
                (f"%{search}%", f"%{search}%")
            )
        else:
            cursor = self.conn.execute("SELECT * FROM participants ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
        
    def update_participant(self, participant_id: str, name: Optional[str] = None, notes: Optional[str] = None) -> None:
        """Update participant fields."""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
            
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
            
        if not updates:
            return
            
        params.append(participant_id)
        
        query = f"UPDATE participants SET {', '.join(updates)} WHERE id = ?"
        with self.conn:
            self.conn.execute(query, params)
            
    def add_session_record(self, participant_id: str, date: str, visit: str, folder: str) -> int:
        """Record a session. Returns the session row id."""
        created_at = datetime.datetime.now().isoformat()
        with self.conn:
            cursor = self.conn.execute(
                "INSERT INTO sessions (participant_id, date, visit, folder, created_at) VALUES (?, ?, ?, ?, ?)",
                (participant_id, date, visit, folder, created_at)
            )
            return cursor.lastrowid
            
    def get_sessions_for_participant(self, participant_id: str) -> List[Dict[str, Any]]:
        """Get all sessions for a participant, most recent first."""
        cursor = self.conn.execute(
            "SELECT * FROM sessions WHERE participant_id = ? ORDER BY created_at DESC",
            (participant_id,)
        )
        return [dict(row) for row in cursor.fetchall()]
        
    def close(self):
        """Close the database connection."""
        self.conn.close()
