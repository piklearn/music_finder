from app.infer import infer_search_template


def test_infer_template_from_common_param():
    url = "https://site.example/search?q=hello+world&page=2"
    assert infer_search_template(url) == "https://site.example/search?q={query}&page=2"


def test_infer_template_prefers_hint():
    url = "https://site.example/find?term=hello&lang=fa"
    assert infer_search_template(url, "hello") == "https://site.example/find?term={query}&lang=fa"


def test_infer_template_leaves_existing_placeholder():
    url = "https://site.example/search?q={query}"
    assert infer_search_template(url) == url


def test_infer_template_without_query_params_is_unchanged():
    url = "https://site.example/browse"
    assert infer_search_template(url) == url
