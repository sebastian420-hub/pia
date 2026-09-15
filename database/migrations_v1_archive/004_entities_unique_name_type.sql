-- entities.name had no uniqueness, so "ON CONFLICT DO NOTHING" was a no-op and
-- concurrent analysts created duplicates. LOCATION is excluded: many real cities
-- share a name (Springfield, San José), so those stay distinguished by geography.

-- 1. Collapse existing non-LOCATION duplicates onto the most-mentioned row.
CREATE TEMP TABLE _dupes AS
SELECT entity_id,
       first_value(entity_id) OVER (
           PARTITION BY lower(name), entity_type
           ORDER BY mention_count DESC, created_at ASC
       ) AS keeper
FROM entities
WHERE entity_type <> 'LOCATION';
DELETE FROM _dupes WHERE entity_id = keeper;

UPDATE entity_relationships r SET entity_a_id = d.keeper
FROM _dupes d
WHERE r.entity_a_id = d.entity_id
  AND NOT EXISTS (
      SELECT 1 FROM entity_relationships x
      WHERE x.entity_a_id = d.keeper AND x.entity_b_id = r.entity_b_id
        AND x.relationship_type = r.relationship_type AND x.client_id = r.client_id);

UPDATE entity_relationships r SET entity_b_id = d.keeper
FROM _dupes d
WHERE r.entity_b_id = d.entity_id
  AND NOT EXISTS (
      SELECT 1 FROM entity_relationships x
      WHERE x.entity_b_id = d.keeper AND x.entity_a_id = r.entity_a_id
        AND x.relationship_type = r.relationship_type AND x.client_id = r.client_id);

UPDATE entities e SET
    mention_count = e.mention_count + s.mentions,
    uir_refs = COALESCE(e.uir_refs, '{}') || COALESCE(s.refs, '{}')
FROM (
    SELECT d.keeper, SUM(x.mention_count) AS mentions,
           array_agg(u) FILTER (WHERE u IS NOT NULL) AS refs
    FROM _dupes d JOIN entities x ON x.entity_id = d.entity_id
    LEFT JOIN LATERAL unnest(x.uir_refs) u ON TRUE
    GROUP BY d.keeper
) s WHERE e.entity_id = s.keeper;

-- Leftover relationships still pointing at losers would have violated the
-- relationship UNIQUE constraint; they cascade-delete with the loser rows.
DELETE FROM entities WHERE entity_id IN (SELECT entity_id FROM _dupes);
DROP TABLE _dupes;

-- 2. Enforce it going forward (partial: LOCATION excluded).
CREATE UNIQUE INDEX IF NOT EXISTS entities_name_type_uq
    ON entities (lower(name), entity_type) WHERE entity_type <> 'LOCATION';
