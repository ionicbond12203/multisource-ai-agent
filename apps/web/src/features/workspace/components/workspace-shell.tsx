"use client";

import { useWorkspace } from "../hooks/use-workspace";
import type { WorkspaceState } from "../lib/workspace-reducer";
import { ChatPanel } from "./chat-panel";
import { EvidencePanel } from "./evidence-panel";
import { KnowledgeSidebar } from "./knowledge-sidebar";

interface WorkspaceShellProps {
  initialState: WorkspaceState;
  suggestedQuestions: string[];
}

/**
 * Three-column layout: knowledge base | chat | evidence.
 * On narrow screens the columns stack with the chat first.
 */
export function WorkspaceShell({ initialState, suggestedQuestions }: WorkspaceShellProps) {
  const { state, evidenceMessage, usableFiles, actions } = useWorkspace({ initialState });
  const activeSourceIndex =
    evidenceMessage && state.focus?.messageId === evidenceMessage.id ? state.focus.sourceIndex : null;

  return (
    <div className="grid flex-1 grid-cols-1 xl:grid-cols-[260px_minmax(0,1fr)_380px]">
      <div className="order-3 xl:order-1">
        <KnowledgeSidebar
          files={state.files}
          onNewChat={actions.newChat}
          onUpload={actions.uploadFiles}
          onToggleFile={actions.toggleFile}
          onRemoveFile={actions.removeFile}
          onRunOcr={actions.runOcr}
        />
      </div>
      <div className="order-1 xl:order-2">
        <ChatPanel
          title={state.conversationTitle}
          messages={state.messages}
          focus={state.focus}
          pending={state.pending}
          error={state.error}
          usableFileCount={usableFiles.length}
          totalFileCount={state.files.length}
          suggestedQuestions={suggestedQuestions}
          onSend={actions.sendMessage}
          onAttach={actions.uploadFiles}
          onSelectCitation={actions.selectCitation}
          onDismissError={actions.dismissError}
        />
      </div>
      <div className="order-2 xl:order-3">
        <EvidencePanel
          message={evidenceMessage}
          activeSourceIndex={activeSourceIndex}
          tab={state.evidenceTab}
          onTabChange={actions.setEvidenceTab}
          onSelectSource={actions.selectCitation}
        />
      </div>
    </div>
  );
}
