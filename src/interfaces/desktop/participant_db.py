import sqlite3
import logging
from typing import List, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class ParticipantDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Simple participants table, just storing the padded number
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS participants (
                    participant_num TEXT PRIMARY KEY
                )
            """)
            
            # Simple sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    participant_num TEXT,
                    visit TEXT,
                    session_id TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (participant_num) REFERENCES participants (participant_num)
                )
            """)
            conn.commit()

    def add_participant(self, participant_num: str):
        p_num = str(participant_num).zfill(2)
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO participants (participant_num) VALUES (?)",
                    (p_num,)
                )
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False

    def get_participants(self) -> List[str]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT participant_num FROM participants ORDER BY participant_num")
            return [row[0] for row in cursor.fetchall()]

    def add_session(self, participant_num: str, visit: str, session_id: str):
        p_num = str(participant_num).zfill(2)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Ensure participant exists
            cursor.execute("INSERT OR IGNORE INTO participants (participant_num) VALUES (?)", (p_num,))
            
            cursor.execute("""
                INSERT INTO sessions (participant_num, visit, session_id)
                VALUES (?, ?, ?)
            """, (p_num, visit, session_id))
            conn.commit()

    def get_sessions(self, participant_num: str) -> List[Dict[str, Any]]:
        p_num = str(participant_num).zfill(2)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, participant_num, visit, session_id, timestamp
                FROM sessions
                WHERE participant_num = ?
                ORDER BY timestamp DESC
            """, (p_num,))
            return [dict(row) for row in cursor.fetchall()]
