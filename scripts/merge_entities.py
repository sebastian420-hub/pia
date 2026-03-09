import logging
from pia.core.database import DatabaseManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def merge_entities(primary_id: str, secondary_id: str, canonical_name: str):
    db = DatabaseManager()
    try:
        logger.info(f"Initiating merge: {secondary_id} INTO {primary_id}")
        
        # 1. Fetch both entities to combine arrays
        p_ent = db.execute_query("SELECT aliases, uir_refs, cluster_refs, mention_count FROM entities WHERE entity_id = %s", (primary_id,), fetch=True)[0]
        s_ent = db.execute_query("SELECT name, aliases, uir_refs, cluster_refs, mention_count FROM entities WHERE entity_id = %s", (secondary_id,), fetch=True)[0]
        
        def parse_pg_array(val):
            if isinstance(val, list): return [str(v) for v in val]
            if isinstance(val, str):
                val = val.strip('{}')
                return val.split(',') if val else []
            return []

        # Combine and deduplicate arrays
        combined_aliases = list(set(parse_pg_array(p_ent['aliases']) + parse_pg_array(s_ent['aliases']) + [s_ent['name']]))
        combined_uirs = list(set(parse_pg_array(p_ent['uir_refs']) + parse_pg_array(s_ent['uir_refs'])))
        combined_clusters = list(set(parse_pg_array(p_ent['cluster_refs']) + parse_pg_array(s_ent['cluster_refs'])))
        new_mentions = (p_ent['mention_count'] or 0) + (s_ent['mention_count'] or 0)

        # 2. Re-point Relationships (A side)
        rels_a = db.execute_query("SELECT relationship_id, entity_b_id, relationship_type FROM entity_relationships WHERE entity_a_id = %s", (secondary_id,), fetch=True)
        for rel in rels_a:
            try:
                db.execute_query("UPDATE entity_relationships SET entity_a_id = %s WHERE relationship_id = %s", (primary_id, rel['relationship_id']))
            except Exception as e:
                logger.warning(f"Constraint collision moving rel A {rel['relationship_id']}: {e}. Deleting duplicate.")
                db.get_connection().rollback() 
                db.execute_query("DELETE FROM entity_relationships WHERE relationship_id = %s", (rel['relationship_id'],))

        # 3. Re-point Relationships (B side)
        rels_b = db.execute_query("SELECT relationship_id, entity_a_id, relationship_type FROM entity_relationships WHERE entity_b_id = %s", (secondary_id,), fetch=True)
        for rel in rels_b:
            try:
                db.execute_query("UPDATE entity_relationships SET entity_b_id = %s WHERE relationship_id = %s", (primary_id, rel['relationship_id']))
            except Exception as e:
                logger.warning(f"Constraint collision moving rel B {rel['relationship_id']}: {e}. Deleting duplicate.")
                db.get_connection().rollback()
                db.execute_query("DELETE FROM entity_relationships WHERE relationship_id = %s", (rel['relationship_id'],))

        # 4. Update the Primary Entity (Cast arrays to UUID)
        db.execute_query("""
            UPDATE entities 
            SET name = %s,
                canonical_name = %s,
                aliases = %s,
                uir_refs = %s::uuid[],
                cluster_refs = %s::uuid[],
                mention_count = %s,
                updated_at = NOW()
            WHERE entity_id = %s
        """, (canonical_name, canonical_name, combined_aliases, combined_uirs, combined_clusters, new_mentions, primary_id))

        # 5. Delete the Secondary Entity
        db.execute_query("DELETE FROM entities WHERE entity_id = %s", (secondary_id,))
        
        logger.info(f"Merge Complete! '{canonical_name}' now has {new_mentions} mentions.")

    except Exception as e:
        logger.error(f"Merge failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Primary: US (0d3008ab-a856-4264-8cf2-219d2679f54a)
    # Secondary: USA (32abe92d-e9b5-4f58-95c0-43924641c634)
    merge_entities(
        primary_id="0d3008ab-a856-4264-8cf2-219d2679f54a",
        secondary_id="32abe92d-e9b5-4f58-95c0-43924641c634",
        canonical_name="United States"
    )
