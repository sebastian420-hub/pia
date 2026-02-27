-- ingest_geonames.sql
-- Ingests raw GeoNames TSV into the Knowledge Graph as LOCATION entities

-- 1. Create a temporary staging table matching the GeoNames TSV format
CREATE TEMP TABLE tmp_geonames (
    geonameid INT,
    name TEXT,
    asciiname TEXT,
    alternatenames TEXT,
    latitude FLOAT,
    longitude FLOAT,
    feature_class TEXT,
    feature_code TEXT,
    country_code TEXT,
    cc2 TEXT,
    admin1 TEXT,
    admin2 TEXT,
    admin3 TEXT,
    admin4 TEXT,
    population BIGINT,
    elevation TEXT,       -- imported as text to handle occasional invalid values
    dem TEXT,             -- digital elevation model
    timezone TEXT,
    modification_date DATE
);

-- 2. Use blazing fast native COPY to load the file
COPY tmp_geonames FROM '/app/cities15000.txt' NULL AS '' DELIMITER E'	';

-- 3. Transform and insert into the permanent entities graph
INSERT INTO entities (
    entity_type,
    name,
    canonical_name,
    aliases,
    description,
    confidence,
    watch_status,
    primary_geo
)
SELECT 
    'LOCATION',
    name,
    asciiname,
    string_to_array(alternatenames, ','),
    'City in ' || COALESCE(country_code, 'Unknown') || '. Population: ' || COALESCE(population::text, '0'),
    0.99,            -- Seeded foundational data gets 99% confidence
    'PASSIVE',       -- We aren't actively watching every city until an event happens
    ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) -- Convert lat/lon to PostGIS geometry
FROM tmp_geonames
WHERE latitude IS NOT NULL AND longitude IS NOT NULL;
