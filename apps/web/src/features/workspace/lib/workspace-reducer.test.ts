import { describe, expect, it } from "vitest";
import { createDemoWorkspaceState, createEmptyWorkspaceState } from "./initial-state";
import { mockAnswer } from "./mock-data";
import {
  NEW_CONVERSATION_TITLE,
  selectEvidenceMessage,
  selectUsableFiles,
  workspaceReducer,
} from "./workspace-reducer";

describe("workspaceReducer", () => {
  it("names the conversation after the first question and marks it pending", () => {
    const state = workspaceReducer(createEmptyWorkspaceState(), {
      type: "message/sent",
      message: { id: "u1", role: "user", content: "What is form QA-07?" },
    });
    expect(state.conversationTitle).toBe("What is form QA-07?");
    expect(state.pending).toBe(true);
  });

  it("focuses the first source of a new answer", () => {
    const answer = { ...mockAnswer, id: "a2" };
    const state = workspaceReducer(
      { ...createEmptyWorkspaceState(), pending: true },
      {
        type: "message/received",
        message: answer,
      },
    );
    expect(state.pending).toBe(false);
    expect(state.focus).toEqual({ messageId: "a2", sourceIndex: 1 });
  });

  it("switches back to the sources tab when a citation is selected", () => {
    const start = { ...createDemoWorkspaceState(), evidenceTab: "trace" as const };
    const state = workspaceReducer(start, {
      type: "citation/selected",
      messageId: mockAnswer.id,
      sourceIndex: 2,
    });
    expect(state.focus).toEqual({ messageId: mockAnswer.id, sourceIndex: 2 });
    expect(state.evidenceTab).toBe("sources");
  });

  it("toggles a file without touching the others", () => {
    const start = createDemoWorkspaceState();
    const state = workspaceReducer(start, { type: "file/toggled", fileId: "file_sop" });
    expect(state.files.find((f) => f.id === "file_sop")?.enabled).toBe(false);
    expect(state.files.find((f) => f.id === "file_halal")?.enabled).toBe(true);
  });

  it("merges partial file updates", () => {
    const start = createDemoWorkspaceState();
    const state = workspaceReducer(start, {
      type: "file/updated",
      fileId: "file_policy",
      status: { kind: "ready", pages: 26, chunks: 74 },
    });
    const file = state.files.find((f) => f.id === "file_policy");
    expect(file?.status).toEqual({ kind: "ready", pages: 26, chunks: 74 });
    expect(file?.remoteId).toBe("file_policy");
  });

  it("clears messages on reset but keeps the knowledge base", () => {
    const state = workspaceReducer(createDemoWorkspaceState(), { type: "conversation/reset" });
    expect(state.messages).toHaveLength(0);
    expect(state.files.length).toBeGreaterThan(0);
    expect(state.conversationTitle).toBe(NEW_CONVERSATION_TITLE);
  });
});

describe("selectors", () => {
  it("only counts enabled, ready files as usable", () => {
    const usable = selectUsableFiles(createDemoWorkspaceState()).map((f) => f.id);
    expect(usable).toEqual(["file_sop", "file_halal"]);
  });

  it("falls back to the latest answer when nothing is focused", () => {
    const state = { ...createDemoWorkspaceState(), focus: null };
    expect(selectEvidenceMessage(state)?.id).toBe(mockAnswer.id);
  });
});
