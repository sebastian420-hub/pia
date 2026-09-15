import json
import os
from datetime import timezone

from pia.models.seismic import SeismicEvent

FIXTURE = os.path.join(os.path.dirname(__file__), "..", "fixtures", "usgs_feature.json")


def test_usgs_feature_parses():
    with open(FIXTURE, encoding="utf-8") as f:
        event = SeismicEvent(**json.load(f))
    assert event.id == "ak0000"
    assert event.lon == -150.12 and event.lat == 61.45 and event.depth == 33.0
    assert event.properties.mag == 4.6


def test_event_time_is_utc_aware():
    with open(FIXTURE, encoding="utf-8") as f:
        event = SeismicEvent(**json.load(f))
    t = event.event_time
    assert t.tzinfo is not None and t.utcoffset() == timezone.utc.utcoffset(None)
    assert int(t.timestamp() * 1000) == 1772000000000
