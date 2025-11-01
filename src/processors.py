# processors.py
import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError

# Built-ins
def p_trim(v, ctx): ...
def p_normalize_space(v, ctx): ...
def p_regex(v, ctx, pattern, group=1, flags=""): ...
def p_to_number(v, ctx, allow_commas=True): ...
def p_to_price(v, ctx, currency="auto"): ...
def _guess_currency(text): ...

BUILTINS = {
    "trim": p_trim,
    "normalize_space": p_normalize_space,
    "regex": p_regex,
    "to_number": p_to_number,
    "to_price": p_to_price,
}

_executor = ThreadPoolExecutor(max_workers=2)

def _run_custom_callable(func, value, context, timeout_ms=500):
    ...

def run_pipeline(value, processors, context, *, dev_mode=False, custom_registry=None):
    ...

def helper_parse_price(text, currency="auto"):
    return p_to_price(text, {}, currency)

def build_context(page_url, html, selector_used, scope, item_index=None):
    return {
        "page_url": page_url,
        "html": html,
        "selector_used": selector_used,
        "scope": scope,
        "item_index": item_index,
        "helpers": {"parse_price": helper_parse_price}
    }
