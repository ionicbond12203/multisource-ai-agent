/** Public entry point of the Workspace feature. Import from here, not from deep paths. */
export { WorkspaceShell } from "./components/workspace-shell";
export { createDemoWorkspaceState, createEmptyWorkspaceState } from "./lib/initial-state";
export { mockSuggestedQuestions } from "./lib/mock-data";
export { isUsingMockApi } from "./api";
