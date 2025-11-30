#!/bin/bash

# Base directory of this project (~/dev/qwsengine)
BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DISPLAY_NUM=99
DISPLAY=:$DISPLAY_NUM

APP_SCRIPT="$BASE_DIR/src/app.py"
LOG_FILE="$BASE_DIR/qwsengine_vnc.log"

###############################################
# SHARED VIRTUALENV FROM PREVIOUS SETUP
###############################################
VENV_PATH="$HOME/dev/pyside6/.venv"

# Activate shared virtual environment
if [ -d "$VENV_PATH" ]; then
    source "$VENV_PATH/bin/activate"
else
    echo "ERROR: Shared virtualenv not found at: $VENV_PATH"
    exit 1
fi


echo "[$(date)] Starting qwsengine via VNC" | tee -a "$LOG_FILE"

# Kill stale processes
pkill -9 x11vnc 2>/dev/null
pkill -9 Xvfb 2>/dev/null
pkill -9 -f "app.py" 2>/dev/null
sleep 1

# Start Xvfb
echo "[$(date)] Starting Xvfb on $DISPLAY" | tee -a "$LOG_FILE"
Xvfb $DISPLAY -screen 0 1920x1080x24 > /dev/null 2>&1 &
XVFB_PID=$!
sleep 2

# Start lightweight window manager
echo "[$(date)] Starting fluxbox window manager" | tee -a "$LOG_FILE"
fluxbox -display $DISPLAY > /dev/null 2>&1 &
WM_PID=$!
sleep 1

# Start VNC server
echo "[$(date)] Starting x11vnc on port 5900" | tee -a "$LOG_FILE"
x11vnc -display $DISPLAY -forever -nopw -geometry 1920x1080 -pointer_mode 1 > /dev/null 2>&1 &
X11VNC_PID=$!
sleep 2

# Launch the PySide6 application
echo "[$(date)] Launching app: $APP_SCRIPT" | tee -a "$LOG_FILE"
export DISPLAY=$DISPLAY
export QT_QPA_PLATFORM=xcb

python3 "$APP_SCRIPT" 2>&1 | tee -a "$LOG_FILE"

echo "[$(date)] App terminated" | tee -a "$LOG_FILE"

# Cleanup
echo "[$(date)] Cleaning up Xvfb, x11vnc, and WM" | tee -a "$LOG_FILE"
kill $X11VNC_PID $XVFB_PID 2>/dev/null
wait $X11VNC_PID $XVFB_PID 2>/dev/null
kill $WM_PID 2>/dev/null

echo "[$(date)] Shutdown complete" | tee -a "$LOG_FILE"
