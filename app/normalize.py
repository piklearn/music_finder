"""Persian/Arabic text normalisation and fuzzy matching used for ranking."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

_CHAR_MAP = {
    "\u064a": "\u06cc",  # ي -> ی
    "\u0649": "\u06cc",  # ى -> ی
    "\u0643": "\u06a9",  # ك -> ک
    "\u0629": "\u0647",  # ة -> ه
    "\u06c0": "\u0647",  # ۀ -> ه
    "\u0624": "\u0648",  # ؤ -> و
    "\u0623": "\u0627",  # أ -> ا
    "\u0625": "\u0627",  # إ -> ا
    "\u0622": "\u0627",  # آ -> ا
    "\u0671": "\u0627",  # ٱ -> ا
    "\u0626": "\u06cc",  # ئ -> ی
    "\u0640": "",  # tatweel
}

_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")
_TRANS = str.maketrans(_CHAR_MAP)
_ZWNJ = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_PUNCT = re.compile(r"[^\w\s\u0600-\u06ff]+", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Words that music sites put around titles but which hurt matching.
_NOISE = {
    "دانلود", "اهنگ", "آهنگ", "موزیک", "ترانه", "جدید", "جدیدترین", "اصلی",
    "کامل", "کیفیت", "با", "و", "از", "در", "به", "برای", "همراه", "متن",
    "mp3", "320", "128", "64", "flac", "هارد", "ریمیکس", "ریمیکس", "بدون",
    "download", "song", "music", "track", "official", "audio", "video",
    "lyrics", "lyric", "full", "new", "remix", "ft", "feat", "featuring",
}

_STOPWORDS = {
    "the", "a", "an", "and", "of", "to", "in", "on", "for", "with", "my",
    "me", "you", "i", "is", "it", "that", "this", "من", "تو", "او", "ما",
    "شما", "آن", "این", "که", "را", "و", "با", "از", "در", "به", "بر",
}


def normalize(text: str | None) -> str:
    """Lowercase, unify Arabic/Persian letters, strip diacritics and punctuation."""
    if not text:
        return ""
    text = str(text)
    text = _DIACRITICS.sub("", text)
    text = _ZWNJ.sub(" ", text)
    text = text.translate(_TRANS)
    text = text.translate(_DIGITS)
    text = text.casefold()
    text = _PUNCT.sub(" ", text)
    text = _SPACES.sub(" ", text).strip()
    return text


def tokens(text: str | None) -> list[str]:
    return [t for t in normalize(text).split(" ") if t]


def clean_title(text: str | None) -> str:
    """Drop site noise (download, mp3, quality...) so titles compare cleanly."""
    return " ".join(t for t in tokens(text) if t not in _NOISE)


def _content_tokens(text: str | None) -> list[str]:
    return [t for t in clean_title(text).split(" ") if t not in _STOPWORDS and len(t) > 1]


def similarity(query: str, candidate: str) -> float:
    """0..1 similarity between the user's query and a candidate string."""
    q = normalize(query)
    c = normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 1.0
    if q in c:
        return 0.95
    return SequenceMatcher(None, q, c).ratio()


def score(query: str, title: str, artist: str = "") -> float:
    """Rank a search hit: token coverage + whole-string similarity + artist bonus."""
    q_tokens = _content_tokens(query)
    if not q_tokens:
        q_tokens = tokens(query)
    if not q_tokens:
        return 0.0

    candidate = f"{title or ''} {artist or ''}"
    c_tokens = set(_content_tokens(candidate)) or set(tokens(candidate))
    if not c_tokens:
        return 0.0

    coverage = sum(1 for t in q_tokens if t in c_tokens) / len(q_tokens)
    ratio = similarity(query, title) if title else 0.0
    artist_ratio = similarity(artist, query) if artist else 0.0

    result = 0.62 * coverage + 0.30 * ratio + 0.08 * artist_ratio
    # genre/artist-only matches should not outrank real title matches
    if artist and normalize(artist) in normalize(query):
        result += 0.05
    return max(0.0, min(1.0, result))
