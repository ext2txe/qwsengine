# scopes.py
# Minimal DOM helpers for local HTML using lxml.html

from __future__ import annotations
from typing import List, Dict, Tuple, Iterable, Optional, Any
from lxml import html as lxml_html, etree


class HtmlDoc:
    """
    Small wrapper so the app can pass around a document and url together.
    """
    def __init__(self, doc: etree._Element, url: str = ""):
        self.doc = doc
        self.url = url


# ----- low-level DOM adapters -----

def _query_css(base_node: etree._Element, css: Optional[str]) -> List[etree._Element]:
    if not css:
        return []
    try:
        return base_node.cssselect(css)
    except Exception:
        return []

def _query_xpath(base_node: etree._Element, xp: Optional[str]) -> List[etree._Element]:
    if not xp:
        return []
    try:
        res = base_node.xpath(xp)
        # filter to elements only
        return [r for r in res if isinstance(r, etree._Element)]
    except Exception:
        return []

def _get_text(node: etree._Element) -> str:
    return node.text_content().strip()

def _get_inner_html(node: etree._Element) -> str:
    parts = []
    for child in node:
        parts.append(etree.tostring(child, encoding="unicode"))
    return "".join(parts)

def _get_attr(node: etree._Element, name: str) -> Optional[str]:
    return node.get(name)

def _prefer_set(nodes_a: List[Any], nodes_b: List[Any]) -> List[Any]:
    if nodes_a and not nodes_b:
        return nodes_a
    if nodes_b and not nodes_a:
        return nodes_b
    if not nodes_a and not nodes_b:
        return []
    # both non-empty: prefer the smaller (closer to 1), else A
    return nodes_a if len(nodes_a) <= len(nodes_b) else nodes_b

def _combine_nodes(nodes_a: List[Any], nodes_b: List[Any]) -> List[Any]:
    seen = set()
    out = []
    for n in nodes_a + nodes_b:
        if id(n) in seen:
            continue
        seen.add(id(n))
        out.append(n)
    return out

def _resolve_path(root: etree._Element, path_fingerprint: str) -> List[etree._Element]:
    # Simple passthrough to xpath if caller gave one as "path"
    try:
        res = root.xpath(path_fingerprint)
        return [r for r in res if isinstance(r, etree._Element)]
    except Exception:
        return []

def _find_by_near_text(root: etree._Element, text_hint: str) -> List[etree._Element]:
    if not text_hint:
        return []
    xp = f"//*[contains(normalize-space(.), '{text_hint}')]"
    try:
        res = root.xpath(xp)
        return [r for r in res if isinstance(r, etree._Element)]
    except Exception:
        return []


# ----- public API -----

def resolve_scope_nodes(page_doc: HtmlDoc, scope: Dict, *, item_nodes: Iterable[etree._Element] | None = None,
                        anchor_cache: Dict | None = None) -> Tuple[List[etree._Element], Dict]:
    t = (scope or {}).get("type", "document")
    if t == "document":
        return [page_doc.doc], {"scope": "document"}

    if t == "item":
        nodes = list(item_nodes or [])
        return nodes, {"scope": "item", "count": len(nodes)}

    if t == "anchor":
        a = (scope or {}).get("anchor", {})
        strat = a.get("strategy", "selector")
        key = ("anchor", strat, a.get("css"), a.get("xpath"), a.get("path"), a.get("text_hint"))
        if anchor_cache is not None and key in anchor_cache:
            return anchor_cache[key], {"scope": "anchor", "strategy": strat, "cached": True}

        if strat == "selector":
            nodes = _query_css(page_doc.doc, a.get("css")) or _query_xpath(page_doc.doc, a.get("xpath"))
        elif strat == "path":
            nodes = _resolve_path(page_doc.doc, a.get("path"))
        elif strat == "text":
            nodes = _find_by_near_text(page_doc.doc, a.get("text_hint"))
        else:
            nodes = []

        if anchor_cache is not None:
            anchor_cache[key] = nodes
        return nodes, {"scope": "anchor", "strategy": strat, "count": len(nodes)}

    return [page_doc.doc], {"scope": "document"}

def evaluate_selector(base_node_or_nodes: Any, selector: Dict, expect: str = "one") -> Tuple[List[etree._Element], Dict]:
    """
    base_node_or_nodes: single node or list of nodes (for expect='many' scoped to multiple)
    """
    meta = {"used": None, "css_count": None, "xpath_count": None}

    def run_on(base_node):
        css, xp = selector.get("css"), selector.get("xpath")
        css_hits = _query_css(base_node, css) if css else []
        meta_local = {"css_count": len(css_hits), "xpath_count": None, "used": None}
        if expect == "one":
            if len(css_hits) == 1:
                meta_local["used"] = "css"
                return css_hits, meta_local
            xp_hits = _query_xpath(base_node, xp) if xp else []
            meta_local["xpath_count"] = len(xp_hits)
            if len(xp_hits) == 1:
                meta_local["used"] = "xpath"
                return xp_hits, meta_local
            chosen = _prefer_set(css_hits, xp_hits)
            meta_local["used"] = "css" if chosen is css_hits else "xpath"
            return chosen, meta_local
        else:
            xp_hits = _query_xpath(base_node, xp) if xp else []
            meta_local["xpath_count"] = len(xp_hits)
            combined = _combine_nodes(css_hits, xp_hits)
            meta_local["used"] = "css+xpath"
            return combined, meta_local

    if isinstance(base_node_or_nodes, list):
        out = []
        last_meta = {}
        for bn in base_node_or_nodes:
            hits, m = run_on(bn)
            out.extend(hits)
            last_meta = m
        return out, last_meta
    else:
        return run_on(base_node_or_nodes)

def extract_value(nodes: List[etree._Element], mode: str, attr: Optional[str]) -> Any:
    if not nodes:
        return None
    if mode == "text":
        return "\n".join(_get_text(n) for n in nodes)
    if mode == "html":
        return "\n".join(_get_inner_html(n) for n in nodes)
    if mode == "attr" and attr:
        vals = [_get_attr(n, attr) for n in nodes]
        return vals[0] if len(vals) == 1 else vals
    return None
