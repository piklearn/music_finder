from app.models import SiteProfile
from app.resolve import build_search_url, find_download_links, parse_results

SEARCH_HTML = """
<html><body>
  <div class="song-row">
    <h2><a href="/song/1">دانلود آهنگ Hello Adele</a></h2>
    <span class="artist">Adele</span>
  </div>
  <div class="song-row">
    <h2><a href="/song/2">Shape of You</a></h2>
    <span class="artist">Ed Sheeran</span>
  </div>
</body></html>
"""

DETAIL_HTML = """
<html><body>
  <h1>Hello</h1>
  <a href="/song/other">آهنگ مشابه</a>
  <a class="dl-btn" href="/files/hello.mp3">دانلود</a>
  <a href="/files/low.mp3">کیفیت پایین</a>
  <audio src="/files/stream.mp3"></audio>
</body></html>
"""

PROFILE = SiteProfile(
    id="demo",
    name="Demo",
    base="https://music.example",
    search_url="https://music.example/search?q={query}",
    result_selector="div.song-row",
    title_selector="h2 a",
    artist_selector=".artist",
    detail_link_selector="h2 a",
    download_selector="a.dl-btn",
)


def test_build_search_url_encodes_query():
    url = build_search_url(PROFILE, "hello world")
    assert url == "https://music.example/search?q=hello+world"


def test_build_search_url_requires_placeholder():
    broken = PROFILE.model_copy(update={"search_url": "https://music.example/search"})
    try:
        build_search_url(broken, "x")
    except ValueError as exc:
        assert "{query}" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError")


def test_parse_results_uses_selectors():
    items = parse_results(SEARCH_HTML, PROFILE, "https://music.example/search?q=hello")
    assert len(items) == 2
    assert items[0]["title"] == "دانلود آهنگ Hello Adele"
    assert items[0]["artist"] == "Adele"
    assert items[0]["detail_url"] == "https://music.example/song/1"


def test_find_download_links_prefers_explicit_selector():
    links = find_download_links(DETAIL_HTML, "https://music.example/song/1", PROFILE)
    assert links[0]["url"] == "https://music.example/files/hello.mp3"
    assert links[0]["origin"] == "selector"
    assert links[0]["kind"] == "direct"


def test_find_download_links_falls_back_to_heuristics():
    links = find_download_links(DETAIL_HTML, "https://music.example/song/1", None)
    urls = [link["url"] for link in links]
    assert any(url.endswith("hello.mp3") for url in urls)
    assert any(url.endswith("stream.mp3") for url in urls)
    assert all("other" not in url for url in urls)
