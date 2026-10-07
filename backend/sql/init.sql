-- =====================================================================
-- Strathmore University Capstone Project
-- "Optimizing Customer Support Operations through a Retrieval-Augmented
--  Generation (RAG) Conversational AI Framework"
-- Author: Priscilla Njoroge (2026)
--
-- Relational Schema: 8 Core Tables (Table 4.1 Specification)
-- =====================================================================

-- 1. Passenger Accounts (Optional guest or registered passenger)
CREATE TABLE IF NOT EXISTS passenger_accounts (
    passenger_id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE,
    full_name VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. Sessions (Anchors guest or authenticated user sessions)
CREATE TABLE IF NOT EXISTS sessions (
    session_id VARCHAR(36) PRIMARY KEY,
    passenger_id VARCHAR(36) REFERENCES passenger_accounts(passenger_id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Conversations (Multi-turn threads, tracking RAG vs Baseline variant)
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL REFERENCES sessions(session_id) ON DELETE CASCADE,
    system_variant VARCHAR(20) DEFAULT 'RAG', -- 'RAG' vs 'BASELINE'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Messages (Turns within a conversation)
CREATE TABLE IF NOT EXISTS messages (
    message_id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. Retrieval Metadata (Audit trail for Chroma chunk citations)
CREATE TABLE IF NOT EXISTS retrieval_metadata (
    retrieval_id VARCHAR(36) PRIMARY KEY,
    message_id VARCHAR(36) NOT NULL REFERENCES messages(message_id) ON DELETE CASCADE,
    chunk_id VARCHAR(100) NOT NULL,
    document_source VARCHAR(255) NOT NULL,
    similarity_score FLOAT,
    chunk_text TEXT,
    retrieved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. Evaluation Scores (RAGAS quantitative metrics scored by LLM Judge)
CREATE TABLE IF NOT EXISTS evaluation_scores (
    evaluation_id VARCHAR(36) PRIMARY KEY,
    conversation_id VARCHAR(36) NOT NULL REFERENCES conversations(conversation_id) ON DELETE CASCADE,
    system_variant VARCHAR(20) NOT NULL, -- 'RAG' vs 'BASELINE'
    pillar VARCHAR(50) NOT NULL,         -- 'Baggage', 'Rebooking', 'Travel Docs', 'Disruptions'
    faithfulness_score FLOAT,
    answer_relevancy_score FLOAT,
    context_recall_score FLOAT,
    evaluated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 7. Staff Accounts (Mandatory authentication for staff document management)
CREATE TABLE IF NOT EXISTS staff_accounts (
    staff_id VARCHAR(36) PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) DEFAULT 'policy_admin',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 8. Document Uploads (Audit log of ingested policy files)
CREATE TABLE IF NOT EXISTS document_uploads (
    upload_id VARCHAR(36) PRIMARY KEY,
    staff_id VARCHAR(36) REFERENCES staff_accounts(staff_id) ON DELETE SET NULL,
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT,
    chunk_count INT DEFAULT 0,
    status VARCHAR(50) DEFAULT 'INDEXED', -- 'UPLOADING', 'INDEXED', 'FAILED'
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indices for performance on foreign keys and lookup queries
CREATE INDEX IF NOT EXISTS idx_sessions_passenger ON sessions(passenger_id);
CREATE INDEX IF NOT EXISTS idx_conversations_session ON conversations(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_message ON retrieval_metadata(message_id);
CREATE INDEX IF NOT EXISTS idx_eval_conversation ON evaluation_scores(conversation_id);
CREATE INDEX IF NOT EXISTS idx_eval_pillar ON evaluation_scores(pillar);
CREATE INDEX IF NOT EXISTS idx_uploads_staff ON document_uploads(staff_id);
