import asyncio
import os
import asyncpg
import json

DB_HOST = "localhost"
DB_PORT = "5432"
DB_USER = "pia"
DB_PASSWORD = "password"
DB_NAME = "pia"

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    
    # 1. Insert some dummy relationship data to test 2-hop
    print("Setting up test data...")
    try:
        # Create entities
        await conn.execute("""
            INSERT INTO entities (name, entity_type, confidence) VALUES
            ('Target A', 'PERSON', 1.0),
            ('Company B', 'ORGANIZATION', 1.0),
            ('Bank C', 'ORGANIZATION', 1.0),
            ('Government D', 'GPE', 1.0)
            ON CONFLICT DO NOTHING;
        """)
        
        # Get their IDs
        ids = {}
        records = await conn.fetch("SELECT entity_id, name FROM entities WHERE name IN ('Target A', 'Company B', 'Bank C', 'Government D')")
        for r in records:
            ids[r['name']] = r['entity_id']
            
        # Create relationships (A -> B -> C -> D)
        if len(ids) == 4:
            await conn.execute("""
                INSERT INTO entity_relationships (entity_a_id, entity_b_id, relationship_type, confidence) VALUES
                ($1, $2, 'OWNER_OF', 0.9),
                ($2, $3, 'HAS_ACCOUNT_AT', 0.8),
                ($3, $4, 'REGULATED_BY', 0.95)
                ON CONFLICT DO NOTHING;
            """, ids['Target A'], ids['Company B'], ids['Bank C'], ids['Government D'])
            
    except Exception as e:
        print(f"Setup error: {e}")

    # 2. The Recursive CTE Query
    print("\nExecuting recursive CTE for 3 hops from 'Target A'...")
    query = """
        WITH RECURSIVE network_graph AS (
            -- Base case: The root entity
            SELECT 
                r.relationship_id,
                r.entity_a_id as source_id,
                r.entity_b_id as target_id,
                r.relationship_type,
                r.confidence,
                1 as hop_level,
                ARRAY[r.entity_a_id, r.entity_b_id] as path
            FROM entity_relationships r
            JOIN entities e ON r.entity_a_id = e.entity_id OR r.entity_b_id = e.entity_id
            WHERE e.name ILIKE $1
            
            UNION
            
            -- Recursive step: Find connections to the current network frontier
            SELECT 
                r.relationship_id,
                r.entity_a_id as source_id,
                r.entity_b_id as target_id,
                r.relationship_type,
                r.confidence,
                ng.hop_level + 1 as hop_level,
                ng.path || CASE WHEN r.entity_a_id = ANY(ng.path) THEN r.entity_b_id ELSE r.entity_a_id END as path
            FROM entity_relationships r
            JOIN network_graph ng ON (r.entity_a_id = ng.source_id OR r.entity_a_id = ng.target_id OR r.entity_b_id = ng.source_id OR r.entity_b_id = ng.target_id)
            WHERE ng.hop_level < $2
            AND NOT (r.entity_a_id = ANY(ng.path) AND r.entity_b_id = ANY(ng.path)) -- Prevent infinite loops
        )
        SELECT DISTINCT
            ng.relationship_id,
            ng.relationship_type,
            ng.confidence,
            ng.hop_level,
            e1.entity_id as source_id,
            e1.name as source_name,
            e1.entity_type as source_type,
            e2.entity_id as target_id,
            e2.name as target_name,
            e2.entity_type as target_type
        FROM network_graph ng
        JOIN entities e1 ON ng.source_id = e1.entity_id
        JOIN entities e2 ON ng.target_id = e2.entity_id
        ORDER BY ng.hop_level;
    """
    
    records = await conn.fetch(query, 'Target A', 3)
    print(f"Found {len(records)} edges across the network:")
    for r in records:
        print(f"Hop {r['hop_level']}: {r['source_name']} [{r['relationship_type']}] -> {r['target_name']}")
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
