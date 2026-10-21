import yaml

from app.profiles import parse_profiles


def test_parse_yaml_config():
    content = yaml.safe_dump(
        {
            "sites": [
                {
                    "id": "demo",
                    "name": "Demo",
                    "search_url": "https://demo.example/search?q={query}",
                    "result_selector": "div.row",
                }
            ]
        },
        allow_unicode=True,
    )
    profiles, errors = parse_profiles(content)
    assert errors == []
    assert len(profiles) == 1
    assert profiles[0].id == "demo"
    assert profiles[0].download_on == "detail"


def test_parse_json_list():
    content = '[{"id": "a", "search_url": "https://a.example/s?q={query}"}]'
    profiles, errors = parse_profiles(content)
    assert errors == []
    assert profiles[0].id == "a"


def test_invalid_entries_are_reported_but_others_kept():
    content = yaml.safe_dump(
        {
            "sites": [
                {"id": "good", "search_url": "https://g.example/s?q={query}"},
                {"id": "bad", "search_url": "https://b.example/s"},
            ]
        }
    )
    profiles, errors = parse_profiles(content)
    assert len(profiles) == 1
    assert errors and "bad" in errors[0]


def test_empty_and_broken_content():
    profiles, errors = parse_profiles("   ")
    assert profiles == [] and errors

    profiles, errors = parse_profiles("just a string")
    assert profiles == [] and errors
