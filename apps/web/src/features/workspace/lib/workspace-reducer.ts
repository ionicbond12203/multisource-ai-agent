import type {
  AssistantMessage,
  ChatMessage,
  EvidenceTab,
  FileStatus,
  KnowledgeFile,
  UserMessage,
} from "../types";

/**
 * All Workspace state lives in this reducer. It is a pure function, so every
 * behaviour can be unit-tested without rendering (see workspace-reducer.test.ts).
 * Side effects (network calls, timers) belong in hooks/use-workspace.ts.
 */

export interface CitationFocus {
  messageId: string;
  sourceIndex: number;
}

export interface WorkspaceState {
  conversationTitle: string;
  files: KnowledgeFile[];
  messages: ChatMessage[];
  /** Which citation the evidence panel is showing. */
  focus: CitationFocus | null;
  evidenceTab: EvidenceTab;
  /** True while waiting for an answer. */
  pending: boolean;
  error: string | null;
}

export type WorkspaceAction =
  | { type: "conversation/reset" }
  | { type: "file/added"; file: KnowledgeFile }
  | { type: "file/updated"; fileId: string; status?: FileStatus; remoteId?: string }
  | { type: "file/toggled"; fileId: string }
  | { type: "file/removed"; fileId: string }
  | { type: "message/sent"; message: UserMessage }
  | { type: "message/received"; message: AssistantMessage }
  | { type: "message/failed"; error: string }
  | { type: "citation/selected"; messageId: string; sourceIndex: number }
  | { type: "evidence/tabChanged"; tab: EvidenceTab }
  | { type: "error/dismissed" };

export const NEW_CONVERSATION_TITLE = "New chat";

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case "conversation/reset":
      return {
        ...state,
        conversationTitle: NEW_CONVERSATION_TITLE,
        messages: [],
        focus: null,
        pending: false,
        error: null,
      };

    case "file/added":
      return { ...state, files: [...state.files, action.file] };

    case "file/updated":
      return {
        ...state,
        files: state.files.map((file) =>
          file.id === action.fileId
            ? {
                ...file,
                ...(action.status && { status: action.status }),
                ...(action.remoteId && { remoteId: action.remoteId }),
              }
            : file,
        ),
      };

    case "file/toggled":
      return {
        ...state,
        files: state.files.map((file) =>
          file.id === action.fileId ? { ...file, enabled: !file.enabled } : file,
        ),
      };

    case "file/removed":
      return { ...state, files: state.files.filter((file) => file.id !== action.fileId) };

    case "message/sent":
      return {
        ...state,
        // The first question names the conversation.
        conversationTitle:
          state.messages.length === 0 ? truncate(action.message.content, 60) : state.conversationTitle,
        messages: [...state.messages, action.message],
        pending: true,
        error: null,
      };

    case "message/received": {
      const firstSource = action.message.sources[0];
      return {
        ...state,
        messages: [...state.messages, action.message],
        pending: false,
        focus: firstSource ? { messageId: action.message.id, sourceIndex: firstSource.index } : null,
        evidenceTab: "sources",
      };
    }

    case "message/failed":
      return { ...state, pending: false, error: action.error };

    case "citation/selected":
      return {
        ...state,
        focus: { messageId: action.messageId, sourceIndex: action.sourceIndex },
        evidenceTab: "sources",
      };

    case "evidence/tabChanged":
      return { ...state, evidenceTab: action.tab };

    case "error/dismissed":
      return { ...state, error: null };

    default: {
      // Compile-time check that every action type is handled above.
      const unhandled: never = action;
      return unhandled;
    }
  }
}

/* ---------- Selectors ---------- */

/** The answer whose sources the evidence panel shows: the focused one, else the latest. */
export function selectEvidenceMessage(state: WorkspaceState): AssistantMessage | null {
  const answers = state.messages.filter((m): m is AssistantMessage => m.role === "assistant");
  if (state.focus) {
    const focused = answers.find((m) => m.id === state.focus?.messageId);
    if (focused) return focused;
  }
  return answers.at(-1) ?? null;
}

/** Files that are processed and switched on, i.e. what the next answer may use. */
export function selectUsableFiles(state: WorkspaceState): KnowledgeFile[] {
  return state.files.filter((file) => file.enabled && file.status.kind === "ready");
}

function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, max - 1).trimEnd()}…`;
}
