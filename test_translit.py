"""Smoke / regression tests for the transliteration engine.

Run with: python3 test_translit.py
Pure-Python (imports src/translit_core.py directly, no Workers runtime needed).
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))


def _load_worker():
    """Import src/worker.py with the Workers-only JS modules stubbed out, so the
    pure-Python transliteration logic can be tested off-platform."""
    class _Stub:
        def __getattr__(self, _):
            return self

        def __call__(self, *a, **k):
            return self

    js = types.ModuleType("js")
    js.Response = js.URL = js.Object = _Stub()
    js.Request = _Stub()
    cache_storage = _Stub()
    cache_storage.default = _Stub()
    js.caches = cache_storage
    sys.modules["js"] = js

    pyodide = types.ModuleType("pyodide")
    ffi = types.ModuleType("pyodide.ffi")
    ffi.to_js = lambda obj, **k: obj
    sys.modules["pyodide"] = pyodide
    sys.modules["pyodide.ffi"] = ffi

    import worker
    return worker


_worker = _load_worker()
transliterate_text = _worker.transliterate_text
transliterate_word = _worker.transliterate_word


# (input word, expected output). These pin behaviour the engine should keep:
# correct nasal finals, digraph handling, segmentation and overrides.
WORD_CASES = [
    ("hello", "哈喽"),       # override
    ("good", "古德"),        # override / vowel-team segmentation
    ("much", "马奇"),        # common table: /mʌtʃ/ -> 马奇
    ("machine", "马什因"),   # common table: /ʃ/ -> 什
    ("strong", "斯特隆"),    # -ong nasal
    ("king", "金"),          # override
    ("song", "松"),          # common table
    ("long", "隆"),          # common table
    ("london", "伦敦"),      # override
    ("nation", "内申"),      # common table: -tion -> 申
    ("red", "雷德"),         # common table: short-e -> ei row
    ("dog", "多格"),         # common table
    ("very", "维里"),        # override
    # Fallback spelling engine (word not in any table): ch digraph survives
    # the c->k cleanup rather than becoming 克赫.
    ("munching", "穆恩奇英"),
]


def main():
    failures = 0
    for word, expected in WORD_CASES:
        got = transliterate_word(word)
        ok = got == expected
        if not ok:
            failures += 1
        print(f"[{'ok' if ok else 'FAIL'}] {word:12} -> {got}"
              + ("" if ok else f"  (expected {expected})"))

    # Hardcoded common-word table (from CMU pronunciations) is consulted.
    assert transliterate_word("nation") == "内申"      # -tion -> 申
    assert transliterate_word("vision") == "韦真"
    assert transliterate_word("working") == "沃克"
    assert _worker.WORD_OVERRIDES["computer"] == transliterate_word("computer")  # override wins
    assert len(_worker.COMMON_WORD_PHONEMES) >= 4000
    # A word in neither table still works via the fallback engine.
    assert transliterate_word("zzyzx")  # nonsense -> non-empty engine output

    # Structural checks that don't pin exact characters.
    assert transliterate_text("hello world") == "哈喽·沃尔德"
    assert transliterate_text("hello world", separator="") == "哈喽沃尔德"
    assert transliterate_text("a, b!") == "阿,比!"  # punctuation preserved
    digit_output = transliterate_text("year 2024")
    assert "2024" not in digit_output
    assert transliterate_text("2024").startswith(transliterate_word("two"))
    assert transliterate_word("twenty") in transliterate_text("2024")
    assert transliterate_text("") == ""

    print(f"\n{len(WORD_CASES) - failures}/{len(WORD_CASES)} word cases passed.")
    if failures:
        sys.exit(1)
    print("All structural assertions passed.")


if __name__ == "__main__":
    main()
