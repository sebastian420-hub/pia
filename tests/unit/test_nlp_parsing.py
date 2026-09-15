import pytest

from pia.core.nlp import ExtractionError, parse_llm_json


def test_plain_json():
    assert parse_llm_json('{"entities": [], "relationships": []}') == {"entities": [], "relationships": []}


def test_markdown_fenced_json():
    text = 'Sure!\n```json\n{"summary": "ok"}\n```\nDone.'
    assert parse_llm_json(text) == {"summary": "ok"}


def test_prose_around_object():
    assert parse_llm_json('Here you go: {"a": 1} hope that helps') == {"a": 1}


@pytest.mark.parametrize("bad", ["", "   ", None, "no json here", "[1, 2, 3]"])
def test_non_object_raises(bad):
    with pytest.raises(ExtractionError):
        parse_llm_json(bad)


def test_truncated_json_raises():
    # what a 500-token cap used to produce on long document chunks
    with pytest.raises(ExtractionError, match="truncated|Invalid"):
        parse_llm_json('{"entities": [{"name": "SpaceX", "type": "ORGANIZATION"}, {"name": "Bo')
