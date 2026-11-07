import { mockAnswer, mockFiles, mockQuestion } from "./mock-data";
import { NEW_CONVERSATION_TITLE, type WorkspaceState } from "./workspace-reducer";

/** Empty workspace with no files or messages. */
export function createEmptyWorkspaceState(): WorkspaceState {
  return {
    conversationTitle: NEW_CONVERSATION_TITLE,
    files: [],
    messages: [],
    focus: null,
    evidenceTab: "sources",
    pending: false,
    error: null,
  };
}

/** Workspace pre-filled with the sample conversation, for the public demo. */
export function createDemoWorkspaceState(): WorkspaceState {
  return {
    ...createEmptyWorkspaceState(),
    conversationTitle: "Cold chain temperature excursions",
    files: mockFiles,
    messages: [mockQuestion, mockAnswer],
    focus: { messageId: mockAnswer.id, sourceIndex: 1 },
  };
}
