# poc.py
# Heuristic repeating-item detector for a local HTML document using lxml.
# Exposes:
#   detect_repeating_items(dom_root) -> List[dict]
#     returns [{css, xpath, count, score}, ...] ranked by score

from __future__ import annotations
from typing import List, Dict, Tuple
from lxml import etree, html as lxml_html
import itertools
import math


def _class_tuple(el) -> Tuple[str, ...]:
    cls = el.get("class", "") or ""
    parts = tuple(sorted(c for c in cls.strip().split() if c))
    return parts


def _css_for(el) -> str:
    """
    Build a reasonable CSS selector using tag + classes; includes nth-of-type
    only for the *container* identification fallback (we avoid nth for generality).
    """
    tag = el.tag.lower()
    cls = _class_tuple(el)
    if cls:
        return f"{tag}." + ".".join(cls)
    return tag


def _xpath_for(el) -> str:
    """
    Build a robust-ish XPath that keys on tag and classes.
    """
    tag = el.tag
    cls = _class_tuple(el)
    if cls:
        # contains all classes
        conds = " and ".join([f"contains(concat(' ', normalize-space(@class), ' '), ' {c} ')" for c in cls])
        return f".//{tag}[{conds}]"
    return f".//{tag}"


def _sibling_signature(el) -> Tuple:
    """
    Signature of a candidate item node: tag, sorted classes, simplified children structure.
    """
    tag = el.tag.lower()
    cls = _class_tuple(el)
    child_tags = tuple(child.tag.lower() for child in el if isinstance(child.tag, str))
    return (tag, cls, child_tags[:8])  # cap for speed


def _enumerate_candidates(dom_root) -> List[etree._Element]:
    """
    Candidate containers are elements that have >= 2 siblings with same signature.
    We walk the tree and detect sibling groups.
    """
    cands: List[etree._Element] = []
    for parent in dom_root.iter():
        if not isinstance(parent.tag, str):
            continue
        groups = {}
        for child in parent:
            if not isinstance(child.tag, str):
                continue
            sig = _sibling_signature(child)
            groups.setdefault(sig, []).append(child)
        for sig, nodes in groups.items():
            if len(nodes) >= 2:
                # add the child *type* as a candidate container (the repeating item)
                cands.extend(nodes)
    return cands


def _score_group(nodes: List[etree._Element]) -> float:
    """
    Simple score: log(count) * class_density * child_struct_sim
    """
    count = len(nodes)
    if count < 2:
        return 0.0
    # class density: more classes → usually card-like
    cls_len = sum(len(_class_tuple(n)) for n in nodes) / count
    # child similarity: average Jaccard of child tag sets
    sets = [set(ch.tag for ch in n if isinstance(ch.tag, str)) for n in nodes]
    sims = []
    for a, b in itertools.combinations(sets, 2):
        inter = len(a & b)
        union = len(a | b) or 1
        sims.append(inter / union)
    child_sim = sum(sims) / len(sims) if sims else 1.0
    return math.log(count + 1.0) * (1.0 + cls_len / 5.0) * child_sim


def detect_repeating_items(dom_root) -> List[Dict]:
    """
    Returns a ranked list of candidate item selectors from the given lxml root.
    """
    # 1) enumerate all repeating sibling groups
    all_nodes = _enumerate_candidates(dom_root)
    if not all_nodes:
        return []

    # 2) group nodes by (tag, classes) - that's our container signature
    buckets: Dict[Tuple, List[etree._Element]] = {}
    for n in all_nodes:
        key = (n.tag.lower(), _class_tuple(n))
        buckets.setdefault(key, []).append(n)

    # 3) build entries with CSS/XPath, counts, and score
    entries: List[Dict] = []
    for (_, _), nodes in buckets.items():
        # choose the most common element (the repeating "card")
        # use first node as representative for selector generation
        rep = nodes[0]
        css = _css_for(rep)
        # IMPORTANT: container-level CSS should not be ".//"
        # We provide CSS for document-level matching (can be scoped later).
        # For XPath, we provide a relative pattern usable under // (caller can scope).
        xpath = f"//{rep.tag}"
        cls = _class_tuple(rep)
        if cls:
            conds = " and ".join([f"contains(concat(' ', normalize-space(@class), ' '), ' {c} ')" for c in cls])
            xpath = f"//{rep.tag}[{conds}]"

        count = len(nodes)
        score = _score_group(nodes)
        entries.append({"css": css, "xpath": xpath, "count": count, "score": float(score)})

    # 4) sort by score desc, then count desc, then CSS length asc
    entries.sort(key=lambda r: (-r["score"], -r["count"], len(r["css"])))
    # 5) unique by CSS to avoid spam
    seen = set()
    uniq = []
    for e in entries:
        if e["css"] in seen:
            continue
        seen.add(e["css"])
        uniq.append(e)

    return uniq[:50]  # enough to display
