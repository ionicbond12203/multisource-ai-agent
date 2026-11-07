/**
 * Domain types for the Workspace feature.
 *
 * These mirror the JSON the backend (FastAPI + LangGraph) is expected to
 * return. If the API contract changes, update this file first; TypeScript will
 * then point at every component that needs to follow.
 */

/* ---------- Knowledge base files ---------- */

/** Backend ingestion pipeline stages, in order. */
export const INGESTION_STAGES = ["parsing", "chunking", "embedding", "indexing"] as const;
export type IngestionStage = (typeof INGESTION_STAGES)[number];

export type FileStatus =
  | { kind: "uploading"; progress: number } // 0–1, real byte progress
  | { kind: "processing"; stage: IngestionStage; progress?: number } // progress within the stage, 0–1
  | { kind: "ready"; pages: number; chunks: number }
  | { kind: "failed"; reason: string; recovery?: "ocr" | "retry" };

export interface KnowledgeFile {
  /** Client-side id, stable for the lifetime of the row. */
  id: string;
  /** Id assigned by the backend once the upload is accepted. Sent to the chat API. */
  remoteId?: string;
  name: string;
  sizeBytes: number;
  status: FileStatus;
  /** Whether answers may use this file. */
  enabled: boolean;
}

/* ---------- Agent runs ---------- */

export type AgentStepStatus = "running" | "done" | "failed";

export interface AgentStep {
  id: string;
  /** LangGraph node name, e.g. "router", "retrieve". */
  node: string;
  summary: string;
  durationMs: number;
  status: AgentStepStatus;
}

export interface AgentRun {
  steps: AgentStep[];
  totalMs: number;
}

/* ---------- Sources and citations ---------- */

export interface SourcePassage {
  text: string;
  /** True when the answer relies on this passage; it is highlighted in the preview. */
  cited: boolean;
}

export interface Source {
  /** Citation number used in the answer text, e.g. 1 for "[1]". */
  index: number;
  fileId: string;
  fileName: string;
  /** Human-readable location, e.g. "Section 4.2 · page 7 of 18". */
  location: string;
  heading?: string;
  /** Retrieval relevance score, 0–1. */
  score: number;
  passages: SourcePassage[];
}

/* ---------- Messages ---------- */

export interface UserMessage {
  id: string;
  role: "user";
  content: string;
}

export interface AssistantMessage {
  id: string;
  role: "assistant";
  /** Markdown. Citations are written as [1], [2] … and must match a `Source.index`. */
  content: string;
  sources: Source[];
  run: AgentRun;
  /** True when every claim in the answer is backed by a cited source. */
  grounded: boolean;
  followUps: string[];
}

export type ChatMessage = UserMessage | AssistantMessage;

export type EvidenceTab = "sources" | "trace" | "chunks";
