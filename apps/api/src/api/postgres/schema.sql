-- Applied at startup. Every statement is safe to run again.

create extension if not exists vector;

create table if not exists documents (
    id          text primary key,
    name        text not null,
    status      jsonb not null,          -- FileStatus, exactly as the API returns it
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table if not exists chunks (
    id           text primary key,
    document_id  text not null references documents (id) on delete cascade,
    file_name    text not null,
    text         text not null,
    page         integer not null,
    page_count   integer not null,
    embedding    vector(768) not null    -- keep in sync with EMBEDDING_DIMENSIONS
);

create index if not exists chunks_document_id_idx on chunks (document_id);

-- No vector index yet: searches only scan the chunks of the selected files,
-- which is exact and fast at demo scale. Add an HNSW index if this grows.
