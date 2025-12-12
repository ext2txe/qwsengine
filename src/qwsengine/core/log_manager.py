import os
from datetime import datetime
from pathlib import Path


class LogManager:
    def __init__(self, config_dir: str, app_name: str = "app"):
        self.config_dir = Path(config_dir)
        self.app_name = app_name
        self.log_dir = self.config_dir / "log"
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_log_file_path(self) -> Path:
        """Generate log file path with format yyyyMMdd_{app}.log"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"{date_str}_{self.app_name}.log"
    
    def _write_log(self, message: str) -> None:
        """Write a timestamped message to the daily log file"""
        timestamp = datetime.now().strftime("%H%M%S.%f")[:-2]  # hhmmss.ffff (4 decimal places)
        log_entry = f"{timestamp} {message}\n"
        
        try:
            log_file = self._get_log_file_path()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)
        except Exception:
            pass  # Silently fail to avoid crashing the application
    
    def log_info(self, where: str, message: str, meta: dict | None = None) -> None:
        """Log an info message with optional metadata"""
        log_msg = f"[{where}] {message}"
        if meta:
            log_msg += f" | {meta}"
        self._write_log(log_msg)
    
    def log_navigation(self, where: str, message: str, meta: dict | None = None) -> None:
        """Log a navigation message (alias for log_info)"""
        self.log_info(where, message, meta)