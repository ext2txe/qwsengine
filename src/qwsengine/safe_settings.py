# ---------------------------------------------------------------------------
# Safe settings shim
# ---------------------------------------------------------------------------
class _SafeSettings:
    def __init__(self, backing=None):
        self._b = backing

    # reads
    def get(self, key, default=None):
        if self._b is None:
            return default
        getter = getattr(self._b, "get", None) or getattr(self._b, "value", None)
        if callable(getter):
            try:
                return getter(key, default)
            except Exception:
                return default
        try:
            return self._b[key] if key in self._b else default
        except Exception:
            return default

    # writes
    def set(self, key, value):
        if self._b is None:
            return
        setter = getattr(self._b, "set", None) or getattr(self._b, "setValue", None)
        if callable(setter):
            try:
                setter(key, value)
            except Exception:
                pass

    # existing logging helpers (keep yours)
    def log_system_event(self, msg, extra=""):
        fn = getattr(self._b, "log_system_event", None)
        if callable(fn):
            try: fn(msg, extra)
            except Exception: pass

    def log_tab_action(self, action, tab_id, details=""):
        fn = getattr(self._b, "log_tab_action", None)
        if callable(fn):
            try: fn(action, tab_id, details)
            except Exception: pass

    def __getattr__(self, name):
        if self._b is not None:
            try:
                return getattr(self._b, name)
            except Exception:
                pass
        def _noop(*args, **kwargs): return None
        return _noop

