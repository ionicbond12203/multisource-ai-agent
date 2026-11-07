import { mockAnswer } from "../lib/mock-data";
import { INGESTION_STAGES, type FileStatus } from "../types";
import type { AskResponse, ChatClient, FileUpdate, IngestionClient } from "./types";

/**
 * In-browser stand-ins for the backend, used when NEXT_PUBLIC_API_URL is not
 * set. They return canned data with realistic delays so the UI can be built
 * and demoed without a server.
 */

const NOT_FOUND_ANSWER: AskResponse = {
  content:
    "I couldn't find this in the files you selected. Try switching on more files in the knowledge base, or upload a document that covers it.",
  sources: [],
  grounded: false,
  followUps: [],
  run: {
    totalMs: 1300,
    steps: [
      { id: "m1", node: "router", summary: "Document question → RAG path", durationMs: 300, status: "done" },
      {
        id: "m2",
        node: "retrieve",
        summary: "No chunks above the relevance threshold",
        durationMs: 1000,
        status: "done",
      },
    ],
  },
};

export const mockChatClient: ChatClient = {
  async ask(request, signal) {
    await wait(1200, signal);
    if (request.fileIds.length === 0) return NOT_FOUND_ANSWER;
    const { content, sources, grounded, followUps, run } = mockAnswer;
    return { content, sources, grounded, followUps, run };
  },
};

export const mockIngestionClient: IngestionClient = {
  async upload(file, onUpdate, signal) {
    for (let step = 1; step <= 5; step += 1) {
      await wait(250, signal);
      onUpdate({ status: { kind: "uploading", progress: step / 5 } });
    }
    onUpdate({ remoteId: `mock_${file.name}` });
    await simulateProcessing(onUpdate, signal, { kind: "ready", pages: 12, chunks: 34 });
  },

  async runOcr(_remoteId, onUpdate, signal) {
    await simulateProcessing(onUpdate, signal, { kind: "ready", pages: 3, chunks: 6 });
  },
};

async function simulateProcessing(
  onUpdate: (update: FileUpdate) => void,
  signal: AbortSignal | undefined,
  finalStatus: FileStatus,
): Promise<void> {
  for (const stage of INGESTION_STAGES) {
    onUpdate({ status: { kind: "processing", stage } });
    await wait(600, signal);
  }
  onUpdate({ status: finalStatus });
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new DOMException("Cancelled", "AbortError"));
    const timer = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(timer);
      reject(new DOMException("Cancelled", "AbortError"));
    });
  });
}
