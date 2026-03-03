-- 07_layer7_feedback.sql

-- ════════════════════════════════════════════════════════════════
-- LAYER 7: AI FEEDBACK & REINFORCEMENT
-- ════════════════════════════════════════════════════════════════
CREATE TABLE ai_feedback (
    feedback_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id         UUID NOT NULL,
    relationship_id   UUID REFERENCES entity_relationships(relationship_id) ON DELETE CASCADE,
    original_subject  TEXT NOT NULL,
    original_predicate TEXT NOT NULL,
    original_object   TEXT NOT NULL,
    feedback_type     TEXT NOT NULL CHECK (feedback_type IN ('CONFIRMED', 'REJECTED_HALLUCINATION', 'REJECTED_WRONG_PREDICATE')),
    human_correction  TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW()
);

-- Index to quickly fetch negative feedback for dynamic prompt injection
CREATE INDEX idx_ai_feedback_client ON ai_feedback(client_id, feedback_type, created_at DESC) WHERE feedback_type LIKE 'REJECTED%';
