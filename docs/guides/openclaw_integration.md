<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# How to integrate OpenClaw agent with initial knowledge graph

This is the integration question — how OpenClaw becomes the live interface to a database that already contains the world. Let me design this precisely.

***

## The Architecture in One Sentence

OpenClaw connects to your knowledge graph through **MCP tools** — a standardized protocol where OpenClaw calls named functions that query PostgreSQL directly, and the results flow back into Kimi K2.5's context window as grounded, evidence-backed knowledge.[^1][^2][^3]

***

## The Three Layers of Integration

```
┌─────────────────────────────────────────────┐
│           YOU (Director)                    │
│   Telegram message / ORACLE terminal        │
└──────────────────┬──────────────────────────┘
                   ↓
┌──────────────────▼──────────────────────────┐
│           OPENCLAW AGENT                    │
│   Receives your message                     │
│   Decides which MCP tools to call           │
│   Orchestrates Kimi K2.5                    │
│   Formats and returns response              │
└──────────────────┬──────────────────────────┘
                   ↓ MCP tool calls
┌──────────────────▼──────────────────────────┐
│           MCP SERVER (pg-mcp)               │
│   Translates tool calls → SQL               │
│   Executes against PostgreSQL               │
│   Returns structured results                │
│   Understands PostGIS + pgvector + AGE      │
└──────────────────┬──────────────────────────┘
                   ↓ SQL queries
┌──────────────────▼──────────────────────────┐
│       POSTGRESQL + KNOWLEDGE GRAPH          │
│   5M seeded entities (Wikidata)             │
│   775K CIA declassified UIRs               │
│   Live UIRs from collector agents           │
│   Entity relationships (Apache AGE)         │
│   Semantic embeddings (pgvector)            │
│   Geographic layer (PostGIS)                │
└─────────────────────────────────────────────┘
```


***

## Step 1 — Set Up the PostgreSQL MCP Server

The MCP server is the bridge between OpenClaw and your database. It exposes PostgreSQL as a set of callable tools with full awareness of your PostGIS, pgvector, and Apache AGE extensions:[^1][^2]

```bash
# Install pg-mcp — the PostgreSQL MCP server with
# native PostGIS + pgvector + graph extension support
npm install -g @pg-mcp/server

# Or use the Docker version (recommended — Cortex manages it)
docker run -d \
  --name pg-mcp \
  --network pia-internal \
  -e DATABASE_URL="postgresql://pia:password@postgres:5432/pia" \
  -p 3333:3333 \
  pg-mcp/server:latest
```

**Configure it to expose your specific schema:**

```json
// pg-mcp-config.json
{
  "database": {
    "url": "postgresql://pia:password@localhost:5432/pia",
    "pool": {
      "max": 10,
      "idleTimeoutMs": 30000
    }
  },
  "extensions": {
    "postgis": true,
    "pgvector": true,
    "timescaledb": true,
    "apache_age": true
  },
  "allowed_schemas": ["public", "ag_catalog"],
  "read_only_mode": false,
  "max_result_rows": 500,
  "query_timeout_ms": 30000
}
```


***

## Step 2 — Define Your MCP Tool Library

This is the most important design step. Every question OpenClaw can answer about your world is a named MCP tool. You define them once — they become OpenClaw's permanent vocabulary for querying your knowledge graph.[^4][^5][^3]

```python
# mcp_tools.py — Your complete MCP tool library
# These are the tools OpenClaw calls to query your world

from fastmcp import FastMCP
import asyncpg
import json

mcp = FastMCP("pia-intelligence")

# ═══════════════════════════════════════════════════════════
# TOOL GROUP 1: KNOWLEDGE GRAPH QUERIES
# "What do we know about X?"
# ═══════════════════════════════════════════════════════════

@mcp.tool()
async def get_entity_profile(name: str) -> dict:
    """
    Retrieve everything the system knows about a named entity.
    Returns: current profile, confidence, watch status,
    threat score, mention count, relationship count,
    confidence history, and top related entities.
    Use this when the Director asks about a specific
    person, organization, location, or vessel.
    """
    async with db.acquire() as conn:
        entity = await conn.fetchrow("""
            SELECT
                e.*,
                ST_Y(e.primary_geo) AS lat,
                ST_X(e.primary_geo) AS lon,
                (SELECT COUNT(*) FROM entity_relationships
                 WHERE entity_a_id = e.entity_id
                    OR entity_b_id = e.entity_id
                ) AS relationship_count,
                (SELECT json_agg(json_build_object(
                    'revised_at', revised_at,
                    'confidence', new_confidence,
                    'reason', revision_reason
                 ) ORDER BY revised_at)
                 FROM entity_profile_history
                 WHERE entity_id = e.entity_id
                 LIMIT 10
                ) AS confidence_history
            FROM entities e
            WHERE e.name ILIKE $1
               OR $1 = ANY(e.aliases)
            LIMIT 1
        """, f"%{name}%")

        if not entity:
            return {"found": False, "name": name}

        # Get relationships from Apache AGE graph
        relationships = await conn.fetch("""
            SELECT * FROM cypher('pia_graph', $$
                MATCH (a:Entity {entity_id: $entity_id})
                      -[r]->(b:Entity)
                RETURN type(r) AS rel_type,
                       b.name AS connected_entity,
                       r.confidence AS confidence
                ORDER BY r.confidence DESC
                LIMIT 10
            $$) AS (rel_type agtype,
                    connected_entity agtype,
                    confidence agtype)
        """)

        return {
            "found": True,
            "entity": dict(entity),
            "relationships": [dict(r) for r in relationships]
        }


@mcp.tool()
async def search_entities_semantic(
    query: str,
    entity_type: str = None,
    limit: int = 10
) -> list:
    """
    Find entities semantically similar to a description or concept.
    Use when the Director asks "who operates in X corridor"
    or "find organizations similar to this description."
    Returns ranked list of matching entities with profiles.
    """
    # Generate embedding for the query
    embedding = await generate_embedding(query)

    type_filter = f"AND entity_type = '{entity_type}'" if entity_type else ""

    async with db.acquire() as conn:
        results = await conn.fetch(f"""
            SELECT
                entity_id, name, entity_type,
                current_profile, confidence, threat_score,
                watch_status, mention_count,
                1 - (embedding <=> $1::vector) AS similarity
            FROM entities
            WHERE embedding IS NOT NULL
              {type_filter}
            ORDER BY embedding <=> $1
            LIMIT $2
        """, embedding, limit)

    return [dict(r) for r in results]


@mcp.tool()
async def traverse_entity_graph(
    entity_name: str,
    hops: int = 2,
    relationship_types: list = None
) -> dict:
    """
    Traverse the knowledge graph from an entity outward.
    Finds all connected entities within N hops.
    Use to discover hidden connections between entities.
    Critical for: "what is connected to X?" analysis.
    Maximum hops: 3 (beyond that, results become noisy).
    """
    rel_filter = ""
    if relationship_types:
        rel_types = "|".join(relationship_types)
        rel_filter = f"[:{rel_types}*1..{hops}]"
    else:
        rel_filter = f"[*1..{hops}]"

    async with db.acquire() as conn:
        graph_results = await conn.fetch(f"""
            SELECT * FROM cypher('pia_graph', $$
                MATCH path = (root:Entity {{name: '{entity_name}'}})
                             -{rel_filter}-(connected:Entity)
                RETURN connected.name AS name,
                       connected.entity_type AS type,
                       connected.confidence AS confidence,
                       connected.threat_score AS threat_score,
                       length(path) AS distance
                ORDER BY connected.threat_score DESC,
                         distance ASC
                LIMIT 50
            $$) AS (name agtype, type agtype,
                    confidence agtype,
                    threat_score agtype,
                    distance agtype)
        """)

    return {
        "root": entity_name,
        "hops": hops,
        "connected": [dict(r) for r in graph_results],
        "total_found": len(graph_results)
    }


# ═══════════════════════════════════════════════════════════
# TOOL GROUP 2: INTELLIGENCE RECORD QUERIES
# "What was collected about X?"
# ═══════════════════════════════════════════════════════════

@mcp.tool()
async def search_intelligence_semantic(
    query: str,
    days_back: int = 30,
    source_types: list = None,
    domain: str = None,
    limit: int = 20
) -> list:
    """
    Semantic search across all intelligence records.
    Finds UIRs by meaning, not just keywords.
    Use for: "find everything related to [topic]"
    Combines semantic similarity + time + domain filters.
    """
    embedding = await generate_embedding(query)

    filters = ["1 - (embedding <=> $1) > 0.65"]
    filters.append(f"created_at > NOW() - INTERVAL '{days_back} days'")
    if source_types:
        types_str = "','".join(source_types)
        filters.append(f"source_type IN ('{types_str}')")
    if domain:
        filters.append(f"domain = '{domain}'")

    where = " AND ".join(filters)

    async with db.acquire() as conn:
        results = await conn.fetch(f"""
            SELECT
                uid, content_headline, content_summary,
                source_type, source_agent, confidence,
                created_at, domain, entities, tags,
                ST_Y(geo) AS lat, ST_X(geo) AS lon,
                1 - (embedding <=> $1::vector) AS similarity
            FROM intelligence_records
            WHERE {where}
            ORDER BY embedding <=> $1
            LIMIT $2
        """, embedding, limit)

    return [dict(r) for r in results]


@mcp.tool()
async def search_intelligence_spatial(
    lat: float,
    lon: float,
    radius_km: float,
    days_back: int = 7,
    source_type: str = None
) -> list:
    """
    Find all intelligence records within a geographic radius.
    Use for: "what happened near [location] recently?"
    Returns records sorted by distance from center point.
    """
    radius_m = radius_km * 1000
    type_filter = f"AND source_type = '{source_type}'" if source_type else ""

    async with db.acquire() as conn:
        results = await conn.fetch(f"""
            SELECT
                uid, content_headline, content_summary,
                source_type, confidence, created_at,
                ST_Y(geo) AS lat, ST_X(geo) AS lon,
                ST_Distance(
                    geo,
                    ST_SetSRID(ST_MakePoint($2, $1), 4326)
                ) / 1000 AS distance_km
            FROM intelligence_records
            WHERE ST_DWithin(
                geo,
                ST_SetSRID(ST_MakePoint($2, $1), 4326),
                $3
            )
            AND created_at > NOW() - INTERVAL '{days_back} days'
            {type_filter}
            ORDER BY distance_km ASC
            LIMIT 50
        """, lat, lon, radius_m)

    return [dict(r) for r in results]


@mcp.tool()
async def get_cluster_detail(cluster_id: str) -> dict:
    """
    Get full detail on an intelligence cluster including
    all constituent UIRs, confidence history, and
    entity connections.
    Use when Director asks for deep dive on a pattern.
    """
    async with db.acquire() as conn:
        cluster = await conn.fetchrow("""
            SELECT ic.*,
                ST_Y(geo_centroid) AS lat,
                ST_X(geo_centroid) AS lon
            FROM intelligence_clusters ic
            WHERE cluster_id = $1
        """, cluster_id)

        uirs = await conn.fetch("""
            SELECT uid, content_headline, source_type,
                   confidence, created_at, entities
            FROM intelligence_records
            WHERE cluster_id = $1
            ORDER BY created_at DESC
        """, cluster_id)

        revisions = await conn.fetch("""
            SELECT revised_at, previous_confidence,
                   new_confidence, confidence_delta,
                   revision_reason, revised_by
            FROM cluster_revisions
            WHERE cluster_id = $1
            ORDER BY revised_at ASC
        """, cluster_id)

    return {
        "cluster": dict(cluster),
        "uirs": [dict(u) for u in uirs],
        "confidence_history": [dict(r) for r in revisions]
    }


# ═══════════════════════════════════════════════════════════
# TOOL GROUP 3: HISTORICAL BASELINE QUERIES
# "What does history tell us about X?"
# ═══════════════════════════════════════════════════════════

@mcp.tool()
async def search_historical_intelligence(
    query: str,
    before_year: int = 2020,
    limit: int = 15
) -> list:
    """
    Search seeded historical intelligence records.
    Includes: CIA declassified documents, ACLED conflict
    data, World Bank indicators, historical OSINT.
    Use when Director needs historical context for
    a current situation.
    Example: "historical CIA assessments of Iran nuclear"
    """
    embedding = await generate_embedding(query)

    async with db.acquire() as conn:
        results = await conn.fetch("""
            SELECT
                uid, content_headline, content_summary,
                source_name, created_at, confidence,
                1 - (embedding <=> $1::vector) AS similarity
            FROM intelligence_records
            WHERE 'historical' = ANY(tags)
              AND EXTRACT(YEAR FROM created_at) < $2
              AND 1 - (embedding <=> $1) > 0.60
            ORDER BY embedding <=> $1
            LIMIT $3
        """, embedding, before_year, limit)

    return [dict(r) for r in results]


@mcp.tool()
async def get_location_history(
    location_name: str,
    topic: str = None
) -> dict:
    """
    Get complete intelligence history for a location.
    Combines: geographic baseline, historical UIRs,
    current live UIRs, and active clusters.
    Gives full temporal picture of a place.
    Use for: "give me everything on the Strait of Hormuz"
    """
    async with db.acquire() as conn:
        # Get location entity from geographic baseline
        location = await conn.fetchrow("""
            SELECT entity_id, name, current_profile,
                   ST_Y(primary_geo) AS lat,
                   ST_X(primary_geo) AS lon
            FROM entities
            WHERE entity_type = 'LOCATION'
              AND (name ILIKE $1 OR $1 = ANY(aliases))
            LIMIT 1
        """, f"%{location_name}%")

        if not location:
            return {"found": False}

        lat, lon = location['lat'], location['lon']

        # Historical records within 200km
        historical = await conn.fetch("""
            SELECT content_headline, source_name,
                   created_at, confidence
            FROM intelligence_records
            WHERE 'historical' = ANY(tags)
              AND ST_DWithin(geo,
                  ST_SetSRID(ST_MakePoint($2, $1), 4326),
                  200000)
            ORDER BY created_at DESC
            LIMIT 10
        """, lat, lon)

        # Current live clusters in area
        clusters = await conn.fetch("""
            SELECT cluster_id, title, confidence,
                   priority, status
            FROM intelligence_clusters
            WHERE ST_DWithin(geo_centroid,
                  ST_SetSRID(ST_MakePoint($2, $1), 4326),
                  200000)
              AND status = 'ACTIVE'
            ORDER BY confidence DESC
        """, lat, lon)

    return {
        "location": dict(location),
        "historical_context": [dict(r) for r in historical],
        "active_clusters": [dict(r) for r in clusters]
    }


# ═══════════════════════════════════════════════════════════
# TOOL GROUP 4: LIVE INTELLIGENCE FEEDS
# "What is happening right now?"
# ═══════════════════════════════════════════════════════════

@mcp.tool()
async def get_morning_brief() -> dict:
    """
    Retrieve today's morning brief digest.
    Returns the full formatted report plus key developments.
    """
    async with db.acquire() as conn:
        brief = await conn.fetchrow("""
            SELECT content, key_developments,
                   cluster_count, uir_count,
                   created_at
            FROM intelligence_digests
            WHERE digest_type = 'DAILY_BRIEF'
              AND period_end::date = CURRENT_DATE
            ORDER BY created_at DESC
            LIMIT 1
        """)
    return dict(brief) if brief else {"found": False}


@mcp.tool()
async def get_active_anomalies(
    priority: str = None,
    domain: str = None
) -> list:
    """
    Get all currently active anomalies and clusters.
    Use for: globe state, alerting, current situation.
    Returns geo-located clusters ready for map display.
    """
    filters = ["status IN ('ACTIVE', 'ESCALATING')"]
    if priority:
        filters.append(f"priority = '{priority}'")
    if domain:
        filters.append(f"domain = '{domain}'")

    where = " AND ".join(filters)

    async with db.acquire() as conn:
        results = await conn.fetch(f"""
            SELECT cluster_id, title, cluster_type,
                   priority, confidence, uir_count,
                   ST_Y(geo_centroid) AS lat,
                   ST_X(geo_centroid) AS lon,
                   geo_radius_km, updated_at
            FROM intelligence_clusters
            WHERE {where}
            ORDER BY priority DESC, confidence DESC
        """)

    return [dict(r) for r in results]


@mcp.tool()
async def get_flight_anomalies(
    hours_back: int = 24,
    min_score: float = 0.7
) -> list:
    """
    Get flagged flight tracks from the last N hours.
    Returns aircraft with anomaly scores above threshold.
    Use for: "any unusual flights lately?"
    """
    async with db.acquire() as conn:
        results = await conn.fetch("""
            SELECT DISTINCT ON (icao24)
                icao24, callsign, squawk,
                ST_Y(position) AS lat,
                ST_X(position) AS lon,
                altitude_ft, anomaly_score, anomaly_type,
                anomaly_flagged_at
            FROM flight_tracks
            WHERE time > NOW() - ($1 || ' hours')::INTERVAL
              AND anomaly_score > $2
            ORDER BY icao24, anomaly_score DESC
        """, str(hours_back), min_score)

    return [dict(r) for r in results]


# ═══════════════════════════════════════════════════════════
# TOOL GROUP 5: SYSTEM & CORTEX TOOLS
# "How is the system doing?"
# ═══════════════════════════════════════════════════════════

@mcp.tool()
async def get_system_health() -> dict:
    """
    Get current system health from Cortex reports.
    Returns: agent heartbeats, storage usage,
    database stats, recent incidents.
    """
    async with db.acquire() as conn:
        # Last task from each agent
        heartbeats = await conn.fetch("""
            SELECT agent,
                   MAX(completed_at) AS last_active,
                   COUNT(*) FILTER (WHERE status = 'FAILED'
                       AND created_at > NOW() - INTERVAL '24h'
                   ) AS failures_24h
            FROM agent_tasks
            WHERE created_at > NOW() - INTERVAL '24h'
            GROUP BY agent
            ORDER BY last_active DESC
        """)

        # Database stats
        db_stats = await conn.fetchrow("""
            SELECT
                (SELECT COUNT(*) FROM intelligence_records)
                    AS total_uirs,
                (SELECT COUNT(*) FROM entities)
                    AS total_entities,
                (SELECT COUNT(*) FROM entity_relationships)
                    AS total_relationships,
                (SELECT COUNT(*) FROM intelligence_clusters
                 WHERE status = 'ACTIVE')
                    AS active_clusters,
                (SELECT COUNT(*) FROM analysis_queue
                 WHERE status = 'PENDING')
                    AS queue_depth
        """)

    return {
        "agent_heartbeats": [dict(h) for h in heartbeats],
        "database": dict(db_stats)
    }


@mcp.tool()
async def director_task(
    instruction: str,
    target_entity: str = None,
    priority: str = "NORMAL"
) -> dict:
    """
    Submit a tasking instruction from the Director.
    Creates an analysis_queue entry for the relevant agent.
    Example: "Deep dive on Al Rashid Air Cargo"
    Example: "Monitor Strait of Malacca more closely"
    Example: "Generate SITREP on Gulf region"
    """
    async with db.acquire() as conn:
        queue_id = await conn.fetchval("""
            INSERT INTO analysis_queue (
                trigger_type, target_type, priority,
                status
            ) VALUES (
                'DIRECTOR_TASKED', 'DOMAIN', $1, 'PENDING'
            )
            RETURNING queue_id
        """, priority)

        # Write HUMINT UIR documenting the Director's instruction
        uid = await conn.fetchval("""
            INSERT INTO intelligence_records (
                source_type, source_agent,
                content_headline, content_summary,
                content_raw, priority, domain, tags
            ) VALUES (
                'HUMINT', 'director',
                $1,
                'Director tasking instruction submitted.',
                $2, $3, 'UNKNOWN',
                ARRAY['director_task', 'humint']
            )
            RETURNING uid
        """,
        f"Director Task: {instruction[:80]}",
        instruction,
        priority)

    return {
        "queued": True,
        "queue_id": str(queue_id),
        "uir_uid": str(uid),
        "message": f"Task queued: {instruction}"
    }
```


***

## Step 3 — Wire OpenClaw to MCP

```json
// OpenClaw agent configuration
// openclaw-config.json

{
  "agent_id": "pia-director-interface",
  "name": "PIA Intelligence Interface",

  "mcp_servers": [
    {
      "name": "pia-database",
      "transport": "http",
      "url": "http://localhost:3333",
      "description": "PIA PostgreSQL intelligence database with knowledge graph",
      "tools": "all"
    }
  ],

  "model": {
    "provider": "local",
    "endpoint": "http://localhost:8080/v1",
    "model": "kimi-k2.5-int4",
    "context_window": 256000,
    "temperature": 0.2
  },

  "system_prompt": "You are the ORACLE interface for the Personal Intelligence Agency. You have access to a knowledge graph containing 5 million seeded entities, 775,000 historical intelligence records, and a continuously growing corpus of live intelligence. Use your MCP tools to retrieve accurate, grounded information before answering. Never answer from memory alone — always query the database. When the Director asks about an entity, use get_entity_profile and traverse_entity_graph. When asked about a location, use get_location_history. When asked about current events, use get_active_anomalies and search_intelligence_semantic. When the Director issues a task, use director_task to queue it. Always cite the UIR uid or entity_id of sources you use.",

  "channels": {
    "telegram": {
      "bot_token": "${TELEGRAM_BOT_TOKEN}",
      "allowed_users": ["${DIRECTOR_TELEGRAM_ID}"]
    }
  },

  "memory": {
    "session_context": true,
    "persist_conversation": true
  }
}
```


***

## Step 4 — The Session Start Protocol

When OpenClaw starts each session — or when you open a conversation — it runs an automatic orientation sequence against your knowledge graph:[^6][^7]

```python
# OpenClaw session initialization
# Runs automatically when a new Director conversation begins

async def session_start_protocol(openclaw_agent):
    """
    Before the Director says a word, OpenClaw orients itself
    in the current state of the world.
    Mirrors real intelligence analyst morning protocols.
    """

    # 1. Get current system health
    health = await openclaw_agent.call_tool("get_system_health")

    # 2. Get today's morning brief
    brief = await openclaw_agent.call_tool("get_morning_brief")

    # 3. Get all active CRITICAL/HIGH anomalies
    anomalies = await openclaw_agent.call_tool(
        "get_active_anomalies",
        priority="HIGH"
    )

    # 4. Get unread alerts from last 6 hours
    recent = await openclaw_agent.call_tool(
        "search_intelligence_semantic",
        query="critical alert anomaly urgent",
        days_back=1,
        limit=5
    )

    # Build orientation context for Kimi K2.5
    context = f"""
    SESSION ORIENTATION — {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}

    SYSTEM STATUS:
    - Total UIRs in corpus: {health['database']['total_uirs']:,}
    - Total entities known: {health['database']['total_entities']:,}
    - Active clusters: {health['database']['active_clusters']}
    - Analysis queue depth: {health['database']['queue_depth']}

    TODAY'S KEY DEVELOPMENTS:
    {chr(10).join(brief.get('key_developments', []))}

    ACTIVE HIGH PRIORITY ANOMALIES: {len(anomalies)}
    {chr(10).join([f"- {a['title']} (conf: {a['confidence']:.2f})" for a in anomalies[:3]])}

    Ready for Director queries.
    """

    return context
```


***

## What This Looks Like In Practice

The Director (you) sends a Telegram message:

**"What do we know about the Strait of Hormuz situation?"**

OpenClaw automatically:

1. Calls `get_location_history("Strait of Hormuz")` → gets PostGIS coordinates, entity profile, historical CIA assessments
2. Calls `search_intelligence_semantic("Strait of Hormuz military vessel activity", days_back=30)` → finds 23 recent UIRs
3. Calls `get_active_anomalies(domain="MARITIME")` → finds 2 active clusters in the region
4. Calls `traverse_entity_graph("Strait of Hormuz", hops=2)` → finds connected entities: Iran, IRGC, 3 tanker companies

Kimi K2.5 reads all four tool responses in its 256K context window — that's the seeded geographic baseline, historical CIA documents from the 1980s, 3 weeks of live maritime intelligence, and the entity relationship graph — all at once.

The response you receive is not a search result. It's a **synthesized intelligence assessment** grounded in your full corpus, citing specific UIR IDs, backed by 40 years of historical context, and connected to every entity in your graph that's relevant.[^3][^8]

***

## The Seeded Knowledge Graph Integration Specifically

Your initial seed data integrates through the **same entity and UIR tables** as live collection. The only difference is tags:

```sql
-- Historical entities (seeded from Wikidata)
-- have source = 'wikidata_seed', tags = ['seeded', 'wikidata']

-- Historical UIRs (seeded from CIA CREST, Gutenberg, ACLED)
-- have tags = ['historical', 'declassified', 'seeded']
-- and created_at = the document's actual date, not today

-- Live UIRs from agents
-- have tags based on their content
-- and created_at = now

-- The MCP tools query BOTH seamlessly
-- semantic search doesn't distinguish — it finds by meaning
-- historical_intelligence tool filters by 'historical' tag
-- location_history tool returns both historical + live
```

This means OpenClaw never knows the difference between knowledge from a 1985 CIA document and knowledge from this morning's OSINT collection. It just knows what your system knows — and your system knows everything, from history to right now.[^7][^6]

That is the integration. The seeded knowledge graph doesn't sit separately from the live system. It **is** the live system's past. Every entity Wikidata gave you is waiting to be confirmed, contradicted, or deepened by live collection. Every CIA document from 1965 is waiting to surface as historical context when a modern event echoes it. The knowledge graph is unified — historical and live, seeded and collected, all searchable by the same MCP tools, all readable in the same Kimi K2.5 context window.
<span style="display:none">[^10][^11][^12][^13][^14][^15][^9]</span>

<div align="center">⁂</div>

[^1]: https://mcpmarket.com/server/pg-mcp

[^2]: https://mcpmarket.com/server/pg

[^3]: https://www.superteams.ai/blog/how-to-build-autonomous-ai-agents-using-anthropic-mcp-mistral-models-and-pgvector

[^4]: https://chat.mcp.so/server/openclaw-fcma/MohitDhawane

[^5]: https://openclawdir.com/plugins/plugin-graph-q8pw54

[^6]: https://www.reddit.com/r/openclaw/comments/1r4hfrz/i_built_a_knowledge_graph_mcp_server_instead_of/

[^7]: https://www.reddit.com/r/openclaw/comments/1r8kkaw/built_a_memory_knowledge_graph_architecture_for/

[^8]: https://www.pgedge.com/blog/introducing-the-pgedge-postgres-mcp-server

[^9]: https://github.com/coolmanns/openclaw-memory-architecture

[^10]: https://www.reddit.com/r/Observability/comments/1qto8rp/mcp_integration_for_querying_logs_metrics_and/

[^11]: https://lobehub.com/mcp/shaneholloman-mcp-knowledge-graph

[^12]: https://www.youtube.com/watch?v=tjEznowIhBo

[^13]: https://github.com/ssmanji89/postgres-mcp-tools

[^14]: https://www.linkedin.com/posts/jochen-madler_mcps-are-dead-every-app-will-become-an-api-activity-7425017156599451648-9nnj

[^15]: https://www.theopenclawtoolkit.com

