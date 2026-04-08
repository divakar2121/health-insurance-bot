-- Health Insurance Bot - Supabase Schema
-- Run this in Supabase SQL Editor

-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    content TEXT,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Chunks table  
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    document_id TEXT REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER,
    text TEXT
);

-- Q&A History
CREATE TABLE IF NOT EXISTS qa_history (
    id TEXT PRIMARY KEY,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    document_id TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE qa_history ENABLE ROW LEVEL SECURITY;

-- Allow public access (for now - can restrict later)
CREATE POLICY "Allow public access documents" ON documents FOR ALL USING (true);
CREATE POLICY "Allow public access chunks" ON chunks FOR ALL USING (true);
CREATE POLICY "Allow public access qa_history" ON qa_history FOR ALL USING (true);