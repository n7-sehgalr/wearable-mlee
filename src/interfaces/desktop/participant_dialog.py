from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QInputDialog, QMessageBox, QTableWidget, QTableWidgetItem,
                             QSplitter, QHeaderView, QWidget)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont

class ParticipantDialog(QDialog):
    """Rich Dialog to view participants and their past session histories."""
    
    participant_selected = pyqtSignal(str)  # Emits participant_num

    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Participant Database")
        self.resize(750, 500)
        
        main_layout = QVBoxLayout(self)
        
        # Splitter to have Participants on left, Sessions on right
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- Left Panel: Participants List ---
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        left_layout.addWidget(QLabel("<b>Participants:</b>"))
        self.list_widget = QListWidget()
        self.list_widget.setFont(QFont("Consolas", 10))
        self.list_widget.itemSelectionChanged.connect(self._on_participant_changed)
        left_layout.addWidget(self.list_widget)
        
        btn_add = QPushButton("Add New Participant")
        btn_add.clicked.connect(self._add_participant)
        left_layout.addWidget(btn_add)
        
        splitter.addWidget(left_widget)
        
        # --- Right Panel: Sessions Table ---
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_sessions = QLabel("<b>Session History:</b>")
        right_layout.addWidget(self.lbl_sessions)
        
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Date / Time", "Visit", "File Prefix (Session ID)"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        right_layout.addWidget(self.table)
        
        splitter.addWidget(right_widget)
        splitter.setSizes([200, 550])
        
        # --- Bottom Panel: Action Buttons ---
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_select = QPushButton("Select Participant for New Recording")
        self.btn_select.setMinimumHeight(35)
        self.btn_select.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_select.clicked.connect(self._select_participant)
        btn_layout.addWidget(self.btn_select)
        
        main_layout.addLayout(btn_layout)
        
        self.refresh_list()
        
    def refresh_list(self):
        self.list_widget.clear()
        participants = self.db.get_participants()
        for p in participants:
            item = QListWidgetItem(f"Participant {p}")
            item.setData(Qt.ItemDataRole.UserRole, p)
            self.list_widget.addItem(item)
            
        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)
            
    def _on_participant_changed(self):
        self.table.setRowCount(0)
        item = self.list_widget.currentItem()
        if not item:
            self.lbl_sessions.setText("<b>Session History:</b>")
            return
            
        p_num = item.data(Qt.ItemDataRole.UserRole)
        self.lbl_sessions.setText(f"<b>Session History for Participant {p_num}:</b>")
        
        sessions = self.db.get_sessions(p_num)
        self.table.setRowCount(len(sessions))
        
        for row, sess in enumerate(sessions):
            self.table.setItem(row, 0, QTableWidgetItem(str(sess['timestamp'])))
            self.table.setItem(row, 1, QTableWidgetItem(f"Visit {sess['visit']}"))
            self.table.setItem(row, 2, QTableWidgetItem(sess['session_id']))
            
    def _add_participant(self):
        num_str, ok = QInputDialog.getText(self, "New Participant", "Enter Participant Number (01-45):")
        if ok and num_str.strip():
            num_str = num_str.strip().zfill(2)
            if self.db.add_participant(num_str):
                self.refresh_list()
                # Select the newly added one
                for i in range(self.list_widget.count()):
                    if self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) == num_str:
                        self.list_widget.setCurrentRow(i)
                        break
            else:
                QMessageBox.warning(self, "Error", "Participant already exists.")
                
    def _select_participant(self):
        item = self.list_widget.currentItem()
        if item:
            p_num = item.data(Qt.ItemDataRole.UserRole)
            self.participant_selected.emit(p_num)
            self.accept()
        else:
            QMessageBox.warning(self, "Warning", "Please select a participant first.")
