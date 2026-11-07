"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import { chatClient, ingestionClient, type ChatClient, type IngestionClient } from "../api";
import { validateUpload } from "../lib/upload-rules";
import {
  selectEvidenceMessage,
  selectUsableFiles,
  workspaceReducer,
  type WorkspaceState,
} from "../lib/workspace-reducer";
import type { EvidenceTab } from "../types";
import { createId } from "@/lib/utils";

interface UseWorkspaceOptions {
  initialState: WorkspaceState;
  /** Injected in tests; defaults to the real or mock client chosen in api/index.ts. */
  chat?: ChatClient;
  ingestion?: IngestionClient;
}

/**
 * Connects the Workspace reducer to the backend. Components call the returned
 * actions and never talk to the API directly.
 */
export function useWorkspace({
  initialState,
  chat = chatClient,
  ingestion = ingestionClient,
}: UseWorkspaceOptions) {
  const [state, dispatch] = useReducer(workspaceReducer, initialState);

  // Async callbacks read the latest state through this ref instead of a stale closure.
  const stateRef = useRef(state);
  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  // Cancel in-flight requests when the page unmounts.
  const controllers = useRef(new Set<AbortController>());
  useEffect(() => {
    const active = controllers.current;
    return () => active.forEach((controller) => controller.abort());
  }, []);

  const startRequest = useCallback(() => {
    const controller = new AbortController();
    controllers.current.add(controller);
    return { signal: controller.signal, finish: () => controllers.current.delete(controller) };
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const question = text.trim();
      const current = stateRef.current;
      if (!question || current.pending) return;

      const history = current.messages.map(({ role, content }) => ({ role, content }));
      const fileIds = selectUsableFiles(current).map((file) => file.remoteId ?? file.id);

      dispatch({ type: "message/sent", message: { id: createId("msg"), role: "user", content: question } });

      const request = startRequest();
      try {
        const answer = await chat.ask({ question, fileIds, history }, request.signal);
        dispatch({
          type: "message/received",
          message: { ...answer, id: createId("msg"), role: "assistant" },
        });
      } catch (error) {
        if (isAbort(error)) return;
        dispatch({
          type: "message/failed",
          error: errorMessage(error, "The answer couldn't be generated. Try again."),
        });
      } finally {
        request.finish();
      }
    },
    [chat, startRequest],
  );

  const uploadFiles = useCallback(
    (files: Iterable<File>) => {
      for (const file of files) {
        const id = createId("file");
        const problem = validateUpload(file);
        dispatch({
          type: "file/added",
          file: {
            id,
            name: file.name,
            sizeBytes: file.size,
            enabled: !problem,
            status: problem ? { kind: "failed", reason: problem } : { kind: "uploading", progress: 0 },
          },
        });
        if (problem) continue;

        const request = startRequest();
        ingestion
          .upload(file, (update) => dispatch({ type: "file/updated", fileId: id, ...update }), request.signal)
          .catch((error: unknown) => {
            if (isAbort(error)) return;
            dispatch({
              type: "file/updated",
              fileId: id,
              status: { kind: "failed", reason: errorMessage(error, "Upload failed"), recovery: "retry" },
            });
          })
          .finally(request.finish);
      }
    },
    [ingestion, startRequest],
  );

  const runOcr = useCallback(
    (fileId: string) => {
      const file = stateRef.current.files.find((f) => f.id === fileId);
      if (!file) return;
      const request = startRequest();
      ingestion
        .runOcr(
          file.remoteId ?? file.id,
          (update) => dispatch({ type: "file/updated", fileId, ...update }),
          request.signal,
        )
        .then(() => {
          // Switch the file on once it has text, unless the user already did.
          if (!stateRef.current.files.find((f) => f.id === fileId)?.enabled) {
            dispatch({ type: "file/toggled", fileId });
          }
        })
        .catch((error: unknown) => {
          if (isAbort(error)) return;
          dispatch({
            type: "file/updated",
            fileId,
            status: { kind: "failed", reason: errorMessage(error, "OCR failed"), recovery: "ocr" },
          });
        })
        .finally(request.finish);
    },
    [ingestion, startRequest],
  );

  return {
    state,
    evidenceMessage: selectEvidenceMessage(state),
    usableFiles: selectUsableFiles(state),
    actions: {
      sendMessage,
      uploadFiles,
      runOcr,
      newChat: () => dispatch({ type: "conversation/reset" }),
      toggleFile: (fileId: string) => dispatch({ type: "file/toggled", fileId }),
      removeFile: (fileId: string) => dispatch({ type: "file/removed", fileId }),
      selectCitation: (messageId: string, sourceIndex: number) =>
        dispatch({ type: "citation/selected", messageId, sourceIndex }),
      setEvidenceTab: (tab: EvidenceTab) => dispatch({ type: "evidence/tabChanged", tab }),
      dismissError: () => dispatch({ type: "error/dismissed" }),
    },
  };
}

export type WorkspaceActions = ReturnType<typeof useWorkspace>["actions"];

function isAbort(error: unknown): boolean {
  return error instanceof DOMException && error.name === "AbortError";
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message ? error.message : fallback;
}
