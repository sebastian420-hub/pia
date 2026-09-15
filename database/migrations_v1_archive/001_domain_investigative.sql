-- document_agent writes domain='INVESTIGATIVE'; the original CHECK rejected it,
-- so every document chunk insert failed silently.
ALTER TABLE intelligence_records DROP CONSTRAINT IF EXISTS intelligence_records_domain_check;
ALTER TABLE intelligence_records ADD CONSTRAINT intelligence_records_domain_check CHECK (domain IN (
    'MILITARY','MARITIME','AVIATION','CYBER',
    'FINANCIAL','POLITICAL','NATURAL','INFRASTRUCTURE',
    'PERSONNEL','INVESTIGATIVE','UNKNOWN'
));
