import type { AssistantMessage, FileStatus } from "../types";

/**
 * The contract between this frontend and the backend.
 * JSON uses camelCase. In FastAPI, Pydantic's `alias_generator=to_camel`
 * produces exactly these shapes.
 */

export interface AskRequest {
  question: string;
  /** Backend ids of the files the answer may use. */
  fileIds: string[];
  /** Earlier turns, oldest first. */
  history: Array<{ role: "user" | "assistant"; content: string }>;
}

/** POST /chat response body. */
export type AskResponse = Omit<AssistantMessage, "id" | "role">;

export interface ChatClient {
  ask(request: AskRequest, signal?: AbortSignal): Promise<AskResponse>;
}

/** Partial update for an uploaded file, pushed to the UI as processing advances. */
export interface FileUpdate {
  status?: FileStatus;
  remoteId?: string;
}

export interface IngestionClient {
  /** Uploads a file and reports progress until it is ready or has failed. */
  upload(file: File, onUpdate: (update: FileUpdate) => void, signal?: AbortSignal): Promise<void>;
  /** Re-processes a scanned file with OCR. */
  runOcr(remoteId: string, onUpdate: (update: FileUpdate) => void, signal?: AbortSignal): Promise<void>;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
