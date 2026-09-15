import pytest

from pia.core.heuristics import classify_domain, classify_priority
from pia.core.text import chunk_text


def test_chunks_overlap_and_cover_everything():
    text = "abcdefghij" * 100  # 1000 chars
    chunks = chunk_text(text, chunk_size=300, overlap=50)
    assert chunks[0] == text[:300]
    assert chunks[1].startswith(text[250:300])  # overlap preserved
    assert "".join(c[50:] if i else c for i, c in enumerate(chunks)) == text


def test_short_text_is_one_chunk():
    assert chunk_text("hello", 1500, 200) == ["hello"]


def test_empty_text_gives_no_chunks():
    assert chunk_text("") == []


@pytest.mark.parametrize("bad", [(0, 0), (100, 100), (100, -1)])
def test_bad_chunk_params(bad):
    with pytest.raises(ValueError):
        chunk_text("x", *bad)


def test_domain_heuristics():
    assert classify_domain("navy deploys missile cruiser") == "MILITARY"
    assert classify_domain("stock market rally as bank reports") == "FINANCIAL"
    assert classify_domain("parliament debates new bill") == "POLITICAL"
    # military wins over financial when both appear
    assert classify_domain("army budget hits stock market") == "MILITARY"
    # whole words only
    assert classify_domain("new vr hardware and software warning") == "POLITICAL"


def test_priority_heuristics():
    assert classify_priority("calm day in the capital") == "NORMAL"
    assert classify_priority("three killed in blast") == "HIGH"
    assert classify_priority("calm day", mission_match=True) == "HIGH"
