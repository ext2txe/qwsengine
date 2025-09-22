import logging
from datetime import datetime
from pathlib import Path

class CustomFileHandler(logging.Handler):
    """Custom logging handler that opens and closes file for each write"""
    def __init__(self, log_file: Path):
        super().__init__()
        self.log_file = Path(log_file)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
                f.flush()
        except Exception:
            # Don't crash the app due to logging issues
            pass


class LogManager:
    def __init__(self, config_dir: Path):
        self.config_dir = Path(config_dir)
        self.log_dir = self.config_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        today = datetime.now().strftime("%Y%m%d")
        self.log_file = self.log_dir / f"{today}_qwsengine.log"

        self._setup_logging()
        self.log("Application starting", "SYSTEM")

    def _setup_logging(self) -> None:
        class QWSEngineFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                timestamp = datetime.now().strftime("%H%M%S.%f")[:-3]  # hhmmss.fff
                return f"{timestamp}: {record.getMessage()}"

        self.logger = logging.getLogger('qwsengine')
        self.logger.setLevel(logging.DEBUG)

        # Remove existing handlers (use a copy of the list!)
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)

        file_handler = CustomFileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(QWSEngineFormatter())

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(QWSEngineFormatter())

        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        self.logger.propagate = False

    def log(self, message: str, level: str = "INFO") -> None:
        if level == "DEBUG":
            self.logger.debug(message)
        elif level == "INFO":
            self.logger.info(message)
        elif level == "WARNING":
            self.logger.warning(message)
        elif level == "ERROR":
            self.logger.error(message)
        elif level == "CRITICAL":
            self.logger.critical(message)
        elif level == "SYSTEM":
            self.logger.info(f"[SYSTEM] {message}")
        elif level == "NAV":
            self.logger.info(f"[NAVIGATION] {message}")
        elif level == "TAB":
            self.logger.info(f"[TAB] {message}")
        elif level == "COOKIE":
            self.logger.info(f"[COOKIE] {message}")
        else:
            self.logger.info(message)

    def log_navigation(self, url, title: str = "", tab_id=None) -> None:
        tab_info = f"Tab-{tab_id} " if tab_id else ""
        self.log(f"{tab_info}Navigated to: {url} | Title: {title}", "NAV")

    def log_tab_action(self, action: str, tab_id=None, details: str = "") -> None:
        tab_info = f"Tab-{tab_id} " if tab_id else ""
        self.log(f"{tab_info}{action} {details}".strip(), "TAB")

    def log_error(self, error_msg: str, context: str = "") -> None:
        full_msg = f"{error_msg}"
        if context:
            full_msg += f" | Context: {context}"
        self.log(full_msg, "ERROR")

    def log_system_event(self, event: str, details: str = "") -> None:
        full_msg = f"{event}"
        if details:
            full_msg += f" | {details}"
        self.log(full_msg, "SYSTEM")

    def get_log_file_path(self) -> str:
        return str(self.log_file)
