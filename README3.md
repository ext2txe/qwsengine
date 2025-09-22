# QWSEngine (Refactored)

2025-09-22   chatGPT did this

This refactors the monolithic `main.py` into a small package where each class lives in its own file.

## Layout

```
qwsengine_refactor/
├─ app.py                     # Entry point (python app.py)
└─ qwsengine/
   ├─ __init__.py
   ├─ logging_utils.py        # CustomFileHandler, LogManager
   ├─ settings.py             # SettingsManager
   ├─ settings_dialog.py      # SettingsDialog
   ├─ browser_tab.py          # BrowserTab
   └─ main_window.py          # BrowserWindow
```

## Run

```bash
python app.py
```

> Requires Python with PySide6 installed.
