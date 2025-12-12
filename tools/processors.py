# processors.py
from __future__ import annotations
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import Any, Dict, List, Tuple, Callable

# ---------- Built-ins ----------

def p_trim(v, ctx):
    return v.strip() if isinstance(v, str) else v

def p_normalize_space(v, ctx):
    return re.sub(r"\s+", " ", v).strip() if isinstance(v, str) else v

def p_regex(v, ctx, pattern, group=1, flags=""):
    if not isinstance(v, str):
        return v
    f = 0
    if "i" in flags: f |= re.I
    m = re.search(pattern, v, flags=f)
    return m.group(group) if m else v

def p_to_number(v, ctx, allow_commas=True):
    if v is None: return None
    s = str(v)
    if allow_commas: s = s.replace(",", "")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    return float(m.group(0)) if m else None

def _guess_currency(text: str) -> str | None:
    if not text: return None
    if "€" in text: return "EUR"
    if "$" in text: return "USD"
    if "£" in text: return "GBP"
    return None

def p_to_price(v, ctx, currency="auto"):
    num = p_to_number(v, ctx)
    if num is None: return None
    cur = currency if currency != "auto" else _guess_currency(str(v))
    return {"amount": num, "currency": cur}

BUILTINS = {
    "trim": p_trim,
    "normalize_space": p_normalize_space,
    "regex": p_regex,
    "to_number": p_to_number,
    "to_price": p_to_price,
}

# ---------- Custom (Dev Mode) ----------

_executor = ThreadPoolExecutor(max_workers=2)

def _run_custom_callable(func: Callable, value, context, timeout_ms=500):
    fut = _executor.submit(func, value, context)
    try:
        return fut.result(timeout=timeout_ms / 1000.0), None
    except TimeoutError:
        fut.cancel()
        return value, "timeout"
    except Exception as e:
        return value, f"error: {e.__class__.__name__}: {e}"

def run_pipeline(value: Any, processors: List[Dict], context: Dict, *, dev_mode: bool = False,
                 custom_registry: Dict[str, Callable] | None = None) -> Tuple[Any, List[Tuple[str, str]]]:
    log: List[Tuple[str, str]] = []
    v = value
    for p in processors or []:
        ptype = p.get("type")
        if ptype in BUILTINS:
            fn = BUILTINS[ptype]
            args = p.get("args", {})
            try:
                v = fn(v, context, **args)
                log.append((ptype, "ok"))
            except Exception as e:
                log.append((ptype, f"error: {e}"))
        elif ptype == "custom":
            name = p.get("name")
            if not dev_mode:
                log.append((f"custom:{name}", "skipped (dev mode off)"))
                continue
            if not custom_registry or name not in custom_registry:
                log.append((f"custom:{name}", "missing"))
                continue
            result, err = _run_custom_callable(custom_registry[name], v, context)
            if err:
                log.append((f"custom:{name}", err))
            else:
                log.append((f"custom:{name}", "ok"))
            v = result
        else:
            log.append((ptype or "unknown", "unknown"))
    return v, log

def helper_parse_price(text, currency="auto"):
    return p_to_price(text, {}, currency)

def build_context(page_url: str, html: str, selector_used: Dict | None, scope: str, item_index: int | None = None):
    return {
        "page_url": page_url,
        "html": html,
        "selector_used": selector_used,
        "scope": scope,
        "item_index": item_index,
        "helpers": {"parse_price": helper_parse_price},
    }
