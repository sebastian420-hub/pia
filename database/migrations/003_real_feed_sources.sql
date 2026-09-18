-- Migration 003: Register real-data feed sources for aviation and maritime agents.
-- Applied idempotently (ON CONFLICT DO NOTHING) so it is safe to re-run.

INSERT INTO sources (source_id, label, kind, trust, country_qid, language, homepage) VALUES
  ('opensky',  'OpenSky Network (ADS-B)',  'SENSOR', 0.85, NULL, NULL, 'https://opensky-network.org'),
  ('aishub',   'AISHub (Live AIS)',        'SENSOR', 0.80, NULL, NULL, 'https://www.aishub.net')
ON CONFLICT (source_id) DO NOTHING;
