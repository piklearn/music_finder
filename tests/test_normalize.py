from app import normalize


def test_normalize_arabic_letters_and_diacritics():
    assert normalize.normalize("عَلِي كَريم") == "علی کریم"
    assert normalize.normalize("آهنگِ جديد") == "اهنگ جدید"


def test_normalize_zwnj_and_persian_digits():
    assert normalize.normalize("می‌روم ۱۲۳") == "می روم 123"
    assert normalize.normalize("  Hello—World!! ") == "hello world"


def test_clean_title_drops_site_noise():
    assert normalize.clean_title("دانلود آهنگ Hello با کیفیت 320") == "hello"


def test_exact_match_scores_high():
    assert normalize.score("Hello", "دانلود آهنگ Hello Adele", "Adele") > 0.8


def test_unrelated_song_scores_low():
    assert normalize.score("Hello", "Shape of You", "Ed Sheeran") < 0.35


def test_missing_fields_are_safe():
    assert normalize.score("", "x") == 0.0
    assert normalize.score("x", "") == 0.0
