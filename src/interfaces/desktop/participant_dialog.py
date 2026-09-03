from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTableWidget, 
                             QTableWidgetItem, QGroupBox, QGridLayout,
                             QMessageBox, QHeaderView, QAbstractItemView,
                             QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from src.interfaces.desktop.participant_db import ParticipantDB

class ParticipantDialog(QDialog):
    """Dialog for selecting or creating participants.
    
    Layout:
    - Top: Search box to filter participants
    - Middle-left: Table of participants (ID, Name, Notes, Created)
    - Middle-right: Selected participant's session history table
    - Bottom-left: 'New Participant' form (ID, Name, Notes fields + Add button)
    - Bottom-right: Buttons: 'Select', 'Resume Session', 'Cancel'
    
    Signals:
    - participant_selected(str, str, str): (participant_id, name, visit)
    - session_resumed(str): folder_path of selected session to resume
    """
    
    participant_selected = pyqtSignal(str, str, str)  # ID, Name, Visit
    session_resumed = pyqtSignal(str)                 # Session folder path
    
    def __init__(self, db: ParticipantDB, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Participant Selection")
        self.resize(850, 600)
        
        main_layout = QVBoxLayout(self)
        
        # Search Box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by ID or Name...")
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)
        
        # Middle Section (Tables)
        tables_layout = QHBoxLayout()
        
        # Participants Table
        part_group = QGroupBox("Participants")
        part_layout = QVBoxLayout()
        self.part_table = QTableWidget(0, 4)
        self.part_table.setHorizontalHeaderLabels(["ID", "Name", "Notes", "Created"])
        self.part_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.part_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.part_table.setSortingEnabled(True)
        self.part_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        part_layout.addWidget(self.part_table)
        part_group.setLayout(part_layout)
        tables_layout.addWidget(part_group)
        
        # Session History Table
        hist_group = QGroupBox("Session History")
        hist_layout = QVBoxLayout()
        self.hist_table = QTableWidget(0, 3)
        self.hist_table.setHorizontalHeaderLabels(["Date", "Visit", "Folder Name"])
        self.hist_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.hist_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.hist_table.setSortingEnabled(True)
        self.hist_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        hist_layout.addWidget(self.hist_table)
        hist_group.setLayout(hist_layout)
        tables_layout.addWidget(hist_group)
        
        main_layout.addLayout(tables_layout)
        
        # Bottom Section
        bottom_layout = QHBoxLayout()
        
        # New Participant Form
        new_part_group = QGroupBox("New Participant")
        new_part_layout = QGridLayout()
        self.new_id = QLineEdit()
        self.new_name = QLineEdit()
        self.new_notes = QLineEdit()
        self.btn_add = QPushButton("Add Participant")
        
        new_part_layout.addWidget(QLabel("ID:"), 0, 0)
        new_part_layout.addWidget(self.new_id, 0, 1)
        new_part_layout.addWidget(QLabel("Name:"), 1, 0)
        new_part_layout.addWidget(self.new_name, 1, 1)
        new_part_layout.addWidget(QLabel("Notes:"), 2, 0)
        new_part_layout.addWidget(self.new_notes, 2, 1)
        new_part_layout.addWidget(self.btn_add, 3, 0, 1, 2)
        new_part_group.setLayout(new_part_layout)
        bottom_layout.addWidget(new_part_group)
        
        # Action Buttons
        actions_layout = QVBoxLayout()
        
        visit_layout = QHBoxLayout()
        visit_layout.addWidget(QLabel("Visit:"))
        self.visit_combo = QComboBox()
        self.visit_combo.addItems(["V1", "V2", "V3", "V4"])
        visit_layout.addWidget(self.visit_combo)
        actions_layout.addLayout(visit_layout)
        
        self.btn_select = QPushButton("Select (Start New Session)")
        self.btn_resume = QPushButton("Resume Selected Session")
        self.btn_cancel = QPushButton("Cancel")
        
        actions_layout.addWidget(self.btn_select)
        actions_layout.addWidget(self.btn_resume)
        actions_layout.addWidget(self.btn_cancel)
        actions_layout.addStretch()
        
        bottom_layout.addLayout(actions_layout)
        main_layout.addLayout(bottom_layout)
        
        # Connect signals
        self.btn_select.clicked.connect(self._on_select)
        self.btn_resume.clicked.connect(self._on_resume)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_add.clicked.connect(self._on_add_participant)
        self.search_input.textChanged.connect(self._refresh_participants)
        self.part_table.currentCellChanged.connect(self._on_participant_clicked)

        self._refresh_participants()

    def _refresh_participants(self):
        """Refresh the participants table with current data from DB."""
        search = self.search_input.text().strip()
        participants = self.db.list_participants(search=search)

        self.part_table.setSortingEnabled(False)
        self.part_table.setRowCount(len(participants))
        for i, p in enumerate(participants):
            self.part_table.setItem(i, 0, QTableWidgetItem(p.get('id', '')))
            self.part_table.setItem(i, 1, QTableWidgetItem(p.get('name', '')))
            self.part_table.setItem(i, 2, QTableWidgetItem(p.get('notes', '')))
            self.part_table.setItem(i, 3, QTableWidgetItem(p.get('created_at', '')))
        self.part_table.setSortingEnabled(True)

    def _on_add_participant(self):
        """Add a new participant from the form fields."""
        p_id = self.new_id.text().strip()
        name = self.new_name.text().strip()
        notes = self.new_notes.text().strip()
        if not p_id:
            QMessageBox.warning(self, "Error", "Participant ID is required.")
            return
        try:
            self.db.add_participant(p_id, name, notes)
            self.new_id.clear()
            self.new_name.clear()
            self.new_notes.clear()
            self._refresh_participants()
        except ValueError as e:
            QMessageBox.warning(self, "Error", str(e))

    def _on_participant_clicked(self, row, _col, _prev_row, _prev_col):
        """Load session history when a participant row is selected."""
        if row < 0:
            return
        p_id = self.part_table.item(row, 0).text()
        sessions = self.db.get_sessions_for_participant(p_id)

        self.hist_table.setSortingEnabled(False)
        self.hist_table.setRowCount(len(sessions))
        for i, s in enumerate(sessions):
            self.hist_table.setItem(i, 0, QTableWidgetItem(s.get('date', '')))
            self.hist_table.setItem(i, 1, QTableWidgetItem(s.get('visit', '')))
            self.hist_table.setItem(i, 2, QTableWidgetItem(s.get('folder', '')))
        self.hist_table.setSortingEnabled(True)

    def _on_select(self):
        row = self.part_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection", "Please select a participant.")
            return
        p_id = self.part_table.item(row, 0).text()
        name = self.part_table.item(row, 1).text()
        visit = self.visit_combo.currentText()
        self.participant_selected.emit(p_id, name, visit)
        self.accept()
        
    def _on_resume(self):
        row = self.hist_table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Selection", "Please select a session from the history to resume.")
            return
        folder = self.hist_table.item(row, 2).text()
        self.session_resumed.emit(folder)
        self.accept()

