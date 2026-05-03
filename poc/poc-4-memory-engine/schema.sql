-- LiveT memory engine schema (draft v0.1)
-- Mirrors docs/10-product-design.md §7.1 ER diagram.
-- Used by:
--   - poc/poc-4-memory-engine/run.py (this PoC)
--   - app/src/core/memory/schema.sql  (production, to be written)
--
-- Conventions:
--   - All time fields are ISO-8601 strings with timezone (NOT epoch ints)
--   - UUIDs are stored as TEXT (RN UUID v4 convenient)
--   - JSON fields are TEXT containing JSON; we don't use JSON1 for portability
--   - Embeddings are 384-d float32, stored via sqlite-vec virtual tables
--
-- Privacy invariants enforced at code level (not DB level):
--   - No raw_audio / wav / pcm columns ever
--   - No raw transcript copies (only LLM-extracted summary + key points)

PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

-- ===== scenarios: one row per scenario session =====
CREATE TABLE IF NOT EXISTS scenarios (
    id           TEXT PRIMARY KEY,        -- uuid v4
    pack         TEXT NOT NULL,           -- 'S1'|'S2'|'S5'|'S8'
    started_at   TEXT NOT NULL,
    ended_at     TEXT,
    mode         TEXT NOT NULL,           -- 'active'|'passive_hint'|'guardian'
    summary      TEXT,                    -- LLM-extracted, NEVER raw transcript
    importance   TEXT,                    -- 'high'|'mid'|'low'
    emotion_avg  INTEGER                  -- avg intensity 1-10, nullable
);
CREATE INDEX IF NOT EXISTS idx_scenarios_started ON scenarios (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_scenarios_pack ON scenarios (pack);

-- ===== events: discrete things that happened =====
CREATE TABLE IF NOT EXISTS events (
    id           TEXT PRIMARY KEY,
    scenario_id  TEXT REFERENCES scenarios(id) ON DELETE CASCADE,
    at           TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT,
    category     TEXT,                    -- 'meeting'|'medical'|'emotion'|'decision'|'daily_summary'
    importance   TEXT,                    -- 'high'|'mid'|'low'
    duration_min INTEGER,
    confidence   TEXT                     -- 'high'|'mid'|'low'
);
CREATE INDEX IF NOT EXISTS idx_events_at ON events (at DESC);
CREATE INDEX IF NOT EXISTS idx_events_scenario ON events (scenario_id);

-- ===== events_vec: vector index for events.title || description =====
-- Created via sqlite-vec virtual table; see run.py
-- CREATE VIRTUAL TABLE events_vec USING vec0(embedding float[384]);

-- ===== persons: people the user interacts with =====
CREATE TABLE IF NOT EXISTS persons (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    role            TEXT,
    contact_hint    TEXT,                 -- e.g. wechat id or "妈妈" relation
    traits_json     TEXT NOT NULL DEFAULT '{}',   -- 关注点 / 避雷点 / 风格 (JSON)
    created_at      TEXT NOT NULL,
    last_seen_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_persons_name ON persons (name);

-- ===== events <-> persons many-to-many =====
CREATE TABLE IF NOT EXISTS event_persons (
    event_id  TEXT NOT NULL REFERENCES events(id)  ON DELETE CASCADE,
    person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, person_id)
);

-- ===== emotions =====
CREATE TABLE IF NOT EXISTS emotions (
    id           TEXT PRIMARY KEY,
    scenario_id  TEXT REFERENCES scenarios(id) ON DELETE CASCADE,
    at           TEXT NOT NULL,
    label        TEXT NOT NULL,           -- 'anxious'|'happy'|...
    intensity    INTEGER NOT NULL,        -- 1-10
    trigger      TEXT
);
CREATE INDEX IF NOT EXISTS idx_emotions_at ON emotions (at DESC);

-- ===== open_loops: pending things to do / follow up =====
CREATE TABLE IF NOT EXISTS open_loops (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    description     TEXT,
    due             TEXT,                 -- ISO date or 'asap'/'this_week'
    status          TEXT NOT NULL DEFAULT 'open',  -- 'open'|'done'|'dropped'
    priority        TEXT,                 -- 'high'|'mid'|'low'
    linked_person_id   TEXT REFERENCES persons(id)   ON DELETE SET NULL,
    linked_scenario_id TEXT REFERENCES scenarios(id) ON DELETE SET NULL,
    created_at      TEXT NOT NULL,
    completed_at    TEXT
);
CREATE INDEX IF NOT EXISTS idx_open_loops_status ON open_loops (status, due);

-- ===== person_notes: append-only log of interactions =====
CREATE TABLE IF NOT EXISTS person_notes (
    id        TEXT PRIMARY KEY,
    person_id TEXT NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    at        TEXT NOT NULL,
    note      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_person_notes_person ON person_notes (person_id, at DESC);

-- ===== media: photos / extracted text (NEVER raw audio) =====
CREATE TABLE IF NOT EXISTS media (
    id         TEXT PRIMARY KEY,
    event_id   TEXT REFERENCES events(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,             -- 'photo'|'audio_summary'|'text'  (NOT raw audio)
    path_local TEXT NOT NULL,             -- relative path under app data dir
    created_at TEXT NOT NULL
);

-- ===== daily_recaps: S8 generated reports =====
CREATE TABLE IF NOT EXISTS daily_recaps (
    date              TEXT PRIMARY KEY,           -- 'YYYY-MM-DD'
    one_liner         TEXT,
    highlights_json   TEXT NOT NULL DEFAULT '[]',
    open_loops_json   TEXT NOT NULL DEFAULT '[]',
    emotion_curve_json TEXT,
    soft_suggestion   TEXT,
    generated_at      TEXT NOT NULL
);
