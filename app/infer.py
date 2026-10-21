"""Guess search/download selectors from one sample page of a site.

The idea: the user teaches the tool *one* site once (a sample search URL and a
sample song page), and the resulting profile works for every other song.
"""

from __future__ import annotations

import re
from collections import defaultdict
from urllib.parse import parse_qs, unquote_plus, urlparse, urlunparse

from selectolax.lexbor import LexborHTMLParser as HTMLParser

from .fetcher import Fetcher
from .resolve import DOWNLOAD_HINT, _href, _text, _absolute
from .verify import AUDIO_EXT_RE

_NAV = re.compile(
    r"(login|signin|sign-in|register|cart|basket|checkout|/tag|tag/|/category|category/|"
    r"/author|/about|/contact|/privacy|/terms|/feed|/rss|/page/|/search|/user|/account)",
    re.I,
)
_VALID_CLASS = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_ARTIST_HINT = re.compile(r"(artist|singer|خواننده|executor|performer|band)", re.I)
_QUERY_KEYS = ("q", "s", "search", "query", "kw", "term", "text", "name", "keyword", "string")


def _sig(node) -> tuple[str, tuple[str, ...]]:
    classes = ((node.attributes or {}).get("class") or "").split()
    return node.tag, tuple(sorted(c for c in classes if _VALID_CLASS.match(c)))


def _css(sig: tuple[str, tuple[str, ...]]) -> str:
    tag, classes = sig
    return tag + "".join(f".{c}" for c in classes)


def _guess_selector(node) -> str:
    attrs = node.attributes or {}
    node_id = attrs.get("id")
    if node_id and _VALID_CLASS.match(node_id):
        return f"#{node_id}"
    classes = [c for c in (attrs.get("class") or "").split() if _VALID_CLASS.match(c)]
    if classes:
        return node.tag + "".join(f".{c}" for c in classes[:2])
    href = attrs.get("href", "")
    if "download" in href.lower():
        return f'{node.tag}[href*="download"]'
    return ""


def infer_search_template(url: str, query_hint: str = "") -> str:
    """Turn a sample search URL into a template with {query}."""
    if "{query}" in url:
        return url
    parsed = urlparse(url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    if not params:
        return url

    chosen = ""
    hint = (query_hint or "").strip()
    if hint:
        for key, values in params.items():
            if any(hint == v or hint in v for v in values):
                chosen = key
                break
    if not chosen:
        for key in _QUERY_KEYS:
            if key in params:
                chosen = key
                break
    if not chosen:
        chosen = max(params, key=lambda k: max((len(v) for v in params[k]), default=0))

    parts = []
    for raw in parsed.query.split("&"):
        key, _, _value = raw.partition("=")
        if unquote_plus(key) == chosen:
            parts.append(f"{key}={{query}}")
        else:
            parts.append(raw)
    return urlunparse(parsed._replace(query="&".join(parts)))


def _looks_like_result_group(items: list[tuple], host: str, base_url: str) -> bool:
    if len(items) < 3:
        return False
    hrefs = {url for _node, url, _block in items}
    if len(hrefs) < 3:
        return False
    for node, url, _block in items:
        if _NAV.search(url) or urlparse(url).netloc != host:
            return False
        if len(_text(node)) < 2:
            return False
    return True


def _has_hint(node, pattern: re.Pattern) -> bool:
    for child in node.css("*"):
        marker = " ".join([
            (child.attributes or {}).get("class", ""),
            (child.attributes or {}).get("id", ""),
        ])
        if pattern.search(marker):
            return True
    return False


async def infer_from_search(fetcher: Fetcher, url: str, query_hint: str = "") -> dict:
    html, final_url = await fetcher.get_text(url)
    tree = HTMLParser(html)
    host = urlparse(final_url).netloc
    base = f"{urlparse(final_url).scheme}://{host}"

    # For every anchor, consider up to three ancestor blocks. A row wrapper
    # (div/li/article) usually carries the artist and image, while the anchor
    # itself only carries the title.
    groups: dict[tuple, list[tuple]] = defaultdict(list)
    for anchor in tree.css("a[href]"):
        href = _href(anchor)
        absolute = _absolute(final_url, href)
        if not absolute or not absolute.startswith("http"):
            continue
        # direct file links are not result rows; the detail inferrer handles them
        if AUDIO_EXT_RE.search(urlparse(absolute).path):
            continue
        anchor_sig = _sig(anchor)
        block = anchor.parent
        depth = 0
        while block is not None and depth < 3:
            depth += 1
            groups[(_sig(block), anchor_sig, depth)].append((anchor, absolute, block))
            block = block.parent

    best = None
    best_score = 0.0
    for key, items in groups.items():
        if not _looks_like_result_group(items, host, base):
            continue
        labels = [_text(node) for node, _url, _block in items]
        avg_len = sum(len(label) for label in labels) / len(labels)
        block_sig, _anchor_sig, depth = key
        block = items[0][2]
        score = len(items) * min(avg_len, 45)
        score -= depth * 45
        if block_sig[0] in ("div", "li", "article", "tr", "section"):
            score += 25
        if _has_hint(block, _ARTIST_HINT):
            score += 180
        if block.css_first("img"):
            score += 30
        if score > best_score:
            best, best_score = key, score

    suggestion: dict = {
        "search_url": infer_search_template(final_url, query_hint),
        "base": base,
        "result_selector": "",
        "title_selector": "",
        "detail_link_selector": "",
        "artist_selector": "",
        "preview": [],
        "notes": [],
    }
    if best is None:
        suggestion["notes"].append(
            "بلوک تکرارشونده‌ای پیدا نشد؛ ممکن است نتایج با جاوااسکریپت ساخته شوند یا صفحه نمونه درست نباشد."
        )
        return suggestion

    block_sig, anchor_sig, depth = best
    items = groups[best]
    block = items[0][2]

    anchor_classes = "".join(f".{c}" for c in anchor_sig[1])
    if anchor_classes:
        link_selector = "a" + anchor_classes
    elif depth > 1 and items[0][0].parent is not None:
        parent_sig = _sig(items[0][0].parent)
        link_selector = (
            _css(parent_sig) + " a"
            if parent_sig[0] not in ("div", "li", "article", "tr", "section")
            else "a"
        )
    else:
        link_selector = "a"

    suggestion["result_selector"] = _css(block_sig)
    suggestion["detail_link_selector"] = link_selector
    suggestion["title_selector"] = link_selector

    # artist node: a descendant of the block whose class/id hints at an artist
    for child in block.css("*"):
        if child.tag == "a":
            continue
        marker = " ".join([
            (child.attributes or {}).get("class", ""),
            (child.attributes or {}).get("id", ""),
        ])
        if _ARTIST_HINT.search(marker):
            suggestion["artist_selector"] = _css(_sig(child))
            break

    suggestion["preview"] = [
        {"title": _text(node), "url": absolute}
        for node, absolute, _b in items[:8]
    ]
    return suggestion


async def infer_from_detail(fetcher: Fetcher, url: str) -> dict:
    html, final_url = await fetcher.get_text(url)
    tree = HTMLParser(html)

    candidates: dict[str, dict] = {}
    for node in tree.css("a[href]"):
        href = _href(node)
        label = _text(node)
        absolute = _absolute(final_url, href)
        if not absolute:
            continue
        score = 0
        if AUDIO_EXT_RE.search(urlparse(absolute).path):
            score += 60
        if DOWNLOAD_HINT.search(absolute):
            score += 30
        if DOWNLOAD_HINT.search(label):
            score += 25
        if score <= 0:
            continue
        selector = _guess_selector(node)
        entry = {
            "url": absolute,
            "label": label,
            "score": score,
            "selector": selector,
        }
        if absolute not in candidates or candidates[absolute]["score"] < score:
            candidates[absolute] = entry

    for node in tree.css("audio[src], audio source[src]"):
        absolute = _absolute(final_url, node.attributes.get("src", ""))
        if absolute:
            candidates.setdefault(
                absolute,
                {"url": absolute, "label": "audio", "score": 80, "selector": "audio"},
            )

    ordered = sorted(candidates.values(), key=lambda c: c["score"], reverse=True)
    best = ordered[0] if ordered else None

    suggestion: dict = {
        "download_selector": best["selector"] if best else "",
        "download_candidates": ordered[:6],
        "notes": [],
    }
    if not best:
        suggestion["notes"].append(
            "هیچ لینک دانلودی در صفحهٔ نمونه پیدا نشد؛ سلکتور را دستی وارد کن یا صفحهٔ آهنگ دیگری را امتحان کن."
        )
    elif not best["selector"]:
        suggestion["notes"].append(
            "لینک پیدا شد اما کلاس مشخصی نداشت؛ از سلکتور پیشنهادی مثل a[href*=\"download\"] استفاده کن."
        )
        suggestion["download_selector"] = 'a[href*="download"]'
    return suggestion


async def infer_all(fetcher: Fetcher, search_url: str, detail_url: str = "", query_hint: str = "") -> dict:
    result = await infer_from_search(fetcher, search_url, query_hint)
    if detail_url:
        detail = await infer_from_detail(fetcher, detail_url)
        result["download_selector"] = detail["download_selector"]
        result["download_candidates"] = detail["download_candidates"]
        result["notes"].extend(detail["notes"])
        result["download_on"] = "detail"
    return result
