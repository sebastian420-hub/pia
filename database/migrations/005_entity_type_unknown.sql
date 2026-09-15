-- Bulk seeds (Wikidata) cannot always determine a type; 'UNKNOWN' is honest,
-- typing every person and city as ORGANIZATION was not.
ALTER TABLE entities DROP CONSTRAINT IF EXISTS entities_entity_type_check;
ALTER TABLE entities ADD CONSTRAINT entities_entity_type_check CHECK (entity_type IN (
    'PERSON','ORGANIZATION','LOCATION','GPE','COUNTRY','VESSEL',
    'AIRCRAFT','DOMAIN','INFRASTRUCTURE','EVENT','UNKNOWN'
));
