"""
Script Management UI for QWS Engine

Provides UI controls for creating, editing, and running scripts
"""

from pathlib import Path
import json

from PySide6.QtCore import Qt, QSize, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, 
    QProgressBar, QTextEdit, QSplitter, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QGroupBox, QStackedWidget,
    QToolButton, QSizePolicy
)

from .script_manager import ScriptManager, Script, NavigateAction


class ScriptManagementWidget(QWidget):
    """Widget for script management and playback"""
    
    def __init__(self, parent=None, main_window=None, settings_manager=None, browser_ops=None):
        super().__init__(parent)
        self.main_window = main_window
        self.settings_manager = settings_manager
        self.browser_ops = browser_ops
        
        # Create script manager
        self.script_manager = ScriptManager(
            main_window=main_window,
            settings_manager=settings_manager,
            browser_ops=browser_ops
        )
        
        # Connect script player signals
        self.script_manager.player.playback_started.connect(self._on_playback_started)
        self.script_manager.player.playback_finished.connect(self._on_playback_finished)
        self.script_manager.player.playback_error.connect(self._on_playback_error)
        self.script_manager.player.action_started.connect(self._on_action_started)
        self.script_manager.player.action_finished.connect(self._on_action_finished)
        
        # Initialize UI
        self._init_ui()
        
        # Load available scripts
        self._load_script_list()
    
    def _init_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Script Management")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Script selection
        script_selection_layout = QHBoxLayout()
        script_selection_layout.addWidget(QLabel("Scripts:"))
        
        self.scripts_combo = QComboBox()
        self.scripts_combo.setMinimumWidth(200)
        script_selection_layout.addWidget(self.scripts_combo)
        
        refresh_button = QToolButton()
        refresh_button.setText("⟳")
        refresh_button.setToolTip("Refresh script list")
        refresh_button.clicked.connect(self._load_script_list)
        script_selection_layout.addWidget(refresh_button)
        
        layout.addLayout(script_selection_layout)
        
        # Playback controls
        playback_group = QGroupBox("Playback Controls")
        playback_layout = QVBoxLayout()
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play")
        self.play_button.setToolTip("Play selected script")
        self.play_button.clicked.connect(self._on_play_clicked)
        buttons_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("⬛ Stop")
        self.stop_button.setToolTip("Stop playback")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self._on_stop_clicked)
        buttons_layout.addWidget(self.stop_button)
        
        playback_layout.addLayout(buttons_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        playback_layout.addWidget(self.progress_bar)
        
        # Current action
        self.action_label = QLabel("Ready")
        self.action_label.setAlignment(Qt.AlignCenter)
        self.action_label.setStyleSheet(
            "padding: 5px; border: 1px solid #ccc; background-color: #f5f5f5; border-radius: 3px;"
        )
        playback_layout.addWidget(self.action_label)
        
        playback_group.setLayout(playback_layout)
        layout.addWidget(playback_group)
        
        # Editing controls
        edit_group = QGroupBox("Script Editor")
        edit_layout = QVBoxLayout()
        
        # Simple text editor for now
        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText("Script JSON will appear here when loaded")
        edit_layout.addWidget(self.script_editor)
        
        # Editor buttons
        editor_buttons = QHBoxLayout()
        
        self.load_button = QPushButton("Load")
        self.load_button.setToolTip("Load selected script for editing")
        self.load_button.clicked.connect(self._on_load_clicked)
        editor_buttons.addWidget(self.load_button)
        
        self.save_button = QPushButton("Save")
        self.save_button.setToolTip("Save changes to script")
        self.save_button.clicked.connect(self._on_save_clicked)
        editor_buttons.addWidget(self.save_button)
        
        self.save_as_button = QPushButton("Save As...")
        self.save_as_button.setToolTip("Save script with a new name")
        self.save_as_button.clicked.connect(self._on_save_as_clicked)
        editor_buttons.addWidget(self.save_as_button)
        
        edit_layout.addLayout(editor_buttons)
        
        edit_group.setLayout(edit_layout)
        layout.addWidget(edit_group)
        
        # Add a section for creating a quick navigation script
        quick_script_group = QGroupBox("Quick Navigation Script")
        quick_script_layout = QVBoxLayout()
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QTextEdit()
        self.url_input.setPlaceholderText("Enter URLs (one per line)")
        self.url_input.setMaximumHeight(80)
        url_layout.addWidget(self.url_input)
        
        quick_script_layout.addLayout(url_layout)
        
        create_button = QPushButton("Create Navigation Script")
        create_button.clicked.connect(self._on_create_navigation_script)
        quick_script_layout.addWidget(create_button)
        
        quick_script_group.setLayout(quick_script_layout)
        layout.addWidget(quick_script_group)
        
        # Log area
        log_group = QGroupBox("Script Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(150)
        log_layout.addWidget(self.log_text)
        
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.clicked.connect(self.log_text.clear)
        log_layout.addWidget(clear_log_button)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
    
    def _load_script_list(self):
        """Load list of available scripts"""
        self.scripts_combo.clear()
        
        script_files = self.script_manager.list_scripts()
        
        if not script_files:
            self.scripts_combo.addItem("No scripts available", None)
            self.play_button.setEnabled(False)
            self.load_button.setEnabled(False)
            return
        
        for script_file in sorted(script_files):
            self.scripts_combo.addItem(script_file)
        
        self.play_button.setEnabled(True)
        self.load_button.setEnabled(True)
    
    def _on_play_clicked(self):
        """Handle play button click"""
        if self.script_manager.player.playing:
            self._log("Already playing a script")
            return
        
        current_script = self.scripts_combo.currentText()
        if not current_script or current_script == "No scripts available":
            self._log("No script selected")
            return
        
        # Play the selected script
        success = self.script_manager.play_script_file(current_script)
        if not success:
            self._log(f"Failed to play script: {current_script}")
    
    def _on_stop_clicked(self):
        """Handle stop button click"""
        self.script_manager.stop_playback()
    
    def _on_load_clicked(self):
        """Handle load button click"""
        current_script = self.scripts_combo.currentText()
        if not current_script or current_script == "No scripts available":
            self._log("No script selected")
            return
        
        try:
            # Load the script file
            script_path = self.script_manager.scripts_dir / current_script
            with open(script_path, "r", encoding="utf-8") as f:
                script_json = json.load(f)
            
            # Display in editor
            self.script_editor.setText(json.dumps(script_json, indent=2))
            self._log(f"Loaded script: {current_script}")
        except Exception as e:
            self._log(f"Error loading script: {str(e)}")
    
    def _on_save_clicked(self):
        """Handle save button click"""
        current_script = self.scripts_combo.currentText()
        if not current_script or current_script == "No scripts available":
            self._log("No script selected")
            return
        
        try:
            # Get script JSON from editor
            script_json = self.script_editor.toPlainText()
            script_data = json.loads(script_json)
            
            # Save the script file
            script_path = self.script_manager.scripts_dir / current_script
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(script_data, f, indent=2)
            
            self._log(f"Saved script: {current_script}")
        except Exception as e:
            self._log(f"Error saving script: {str(e)}")
    
    def _on_save_as_clicked(self):
        """Handle save as button click"""
        try:
            # Get script JSON from editor
            script_json = self.script_editor.toPlainText()
            script_data = json.loads(script_json)
            
            # Show save dialog
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save Script As",
                str(self.script_manager.scripts_dir),
                "Script Files (*.json);;All Files (*.*)"
            )
            
            if not file_path:
                return
            
            # Ensure file has .json extension
            if not file_path.lower().endswith(".json"):
                file_path += ".json"
            
            # Save the script file
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(script_data, f, indent=2)
            
            self._log(f"Saved script as: {Path(file_path).name}")
            
            # Refresh script list
            self._load_script_list()
            
            # Select the new script
            new_script_name = Path(file_path).name
            index = self.scripts_combo.findText(new_script_name)
            if index >= 0:
                self.scripts_combo.setCurrentIndex(index)
        except Exception as e:
            self._log(f"Error saving script: {str(e)}")
    
    def _on_create_navigation_script(self):
        """Handle create navigation script button click"""
        # Get URLs from input
        urls_text = self.url_input.toPlainText().strip()
        if not urls_text:
            self._log("No URLs entered")
            return
        
        # Split by newlines
        urls = [url.strip() for url in urls_text.split("\n") if url.strip()]
        
        # Create a new script
        script = Script("Navigation Script")
        
        # Add navigate actions for each URL
        for url in urls:
            script.add_action(NavigateAction(url))
        
        # Show save dialog
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Navigation Script",
            str(self.script_manager.scripts_dir),
            "Script Files (*.json);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        # Ensure file has .json extension
        if not file_path.lower().endswith(".json"):
            file_path += ".json"
        
        # Save the script
        script.save(Path(file_path))
        
        self._log(f"Created navigation script: {Path(file_path).name}")
        
        # Clear URL input
        self.url_input.clear()
        
        # Refresh script list
        self._load_script_list()
        
        # Select the new script
        new_script_name = Path(file_path).name
        index = self.scripts_combo.findText(new_script_name)
        if index >= 0:
            self.scripts_combo.setCurrentIndex(index)
            
        # Load the new script into the editor
        self._on_load_clicked()
    
    def _on_playback_started(self, script):
        """Handle playback started signal"""
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.progress_bar.setValue(0)
        self.action_label.setText("Starting playback...")
        self._log(f"Started playback of script: {script.name}")
    
    def _on_playback_finished(self, script, success):
        """Handle playback finished signal"""
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.progress_bar.setValue(100)
        
        status = "successfully" if success else "with errors"
        self.action_label.setText(f"Playback finished {status}")
        self._log(f"Finished playback of script: {script.name} ({status})")
    
    def _on_playback_error(self, error, action):
        """Handle playback error signal"""
        self.action_label.setText(f"Error: {error}")
        self._log(f"Error: {error}")
    
    def _on_action_started(self, index, action):
        """Handle action started signal"""
        progress = int((index / len(self.script_manager.player.current_script.actions)) * 100)
        self.progress_bar.setValue(progress)
        
        self.action_label.setText(f"Executing: {action.action_type}")
        self._log(f"Started action {index+1}: {action.action_type}")
    
    def _on_action_finished(self, index, action):
        """Handle action finished signal"""
        progress = int(((index + 1) / len(self.script_manager.player.current_script.actions)) * 100)
        self.progress_bar.setValue(progress)
        
        self.action_label.setText(f"Completed: {action.action_type}")
        self._log(f"Completed action {index+1}: {action.action_type}")
    
    def _log(self, message):
        """Add a message to the log"""
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
