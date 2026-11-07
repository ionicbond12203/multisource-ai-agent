import type { FileStatus } from "../types";
import {
  ApiError,
  type AskRequest,
  type AskResponse,
  type ChatClient,
  type FileUpdate,
  type IngestionClient,
} from "./types";

/**
 * Real clients that talk to the FastAPI backend.
 *
 * Endpoints (relative to NEXT_PUBLIC_API_URL):
 *   POST /chat                     AskRequest            -> AskResponse
 *   POST /documents                multipart "file"      -> { id: string, status: FileStatus }
 *   GET  /documents/{id}                                 -> { id: string, status: FileStatus }
 *   POST /documents/{id}/ocr                             -> { id: string, status: FileStatus }
 */

const POLL_INTERVAL_MS = 1500;

export function createHttpChatClient(baseUrl: string): ChatClient {
  return {
    async ask(request: AskRequest, signal?: AbortSignal): Promise<AskResponse> {
      const response = await fetch(`${baseUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(request),
        signal,
      });
      if (!response.ok) {
        throw new ApiError(await readError(response), response.status);
      }
      return (await response.json()) as AskResponse;
    },
  };
}

export function createHttpIngestionClient(baseUrl: string): IngestionClient {
  return {
    async upload(file, onUpdate, signal) {
      const created = await uploadWithProgress(`${baseUrl}/documents`, file, onUpdate, signal);
      onUpdate({ remoteId: created.id, status: created.status });
      await pollUntilSettled(baseUrl, created.id, created.status, onUpdate, signal);
    },

    async runOcr(remoteId, onUpdate, signal) {
      const response = await fetch(`${baseUrl}/documents/${encodeURIComponent(remoteId)}/ocr`, {
        method: "POST",
        signal,
      });
      if (!response.ok) throw new ApiError(await readError(response), response.status);
      const body = (await response.json()) as DocumentResponse;
      onUpdate({ status: body.status });
      await pollUntilSettled(baseUrl, remoteId, body.status, onUpdate, signal);
    },
  };
}

interface DocumentResponse {
  id: string;
  status: FileStatus;
}

/** fetch() cannot report upload progress, so this uses XMLHttpRequest. */
function uploadWithProgress(
  url: string,
  file: File,
  onUpdate: (update: FileUpdate) => void,
  signal?: AbortSignal,
): Promise<DocumentResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", url);
    xhr.responseType = "json";

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) {
        onUpdate({ status: { kind: "uploading", progress: event.loaded / event.total } });
      }
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve(xhr.response as DocumentResponse);
      else reject(new ApiError(`Upload failed (${xhr.status})`, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("Network error during upload"));
    signal?.addEventListener("abort", () => {
      xhr.abort();
      reject(new DOMException("Upload cancelled", "AbortError"));
    });

    const body = new FormData();
    body.append("file", file);
    xhr.send(body);
  });
}

async function pollUntilSettled(
  baseUrl: string,
  id: string,
  initial: FileStatus,
  onUpdate: (update: FileUpdate) => void,
  signal?: AbortSignal,
): Promise<void> {
  let status = initial;
  while (status.kind !== "ready" && status.kind !== "failed") {
    await wait(POLL_INTERVAL_MS, signal);
    const response = await fetch(`${baseUrl}/documents/${encodeURIComponent(id)}`, { signal });
    if (!response.ok) throw new ApiError(await readError(response), response.status);
    status = ((await response.json()) as DocumentResponse).status;
    onUpdate({ status });
  }
}

async function readError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
  } catch {
    // Body was not JSON; fall through to the generic message.
  }
  return `Request failed (${response.status})`;
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    });
  });
}
