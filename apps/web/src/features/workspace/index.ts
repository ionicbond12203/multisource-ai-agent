/** Public entry point of the Workspace feature. Import from here, not from deep paths. */
export { WorkspaceShell } from "./components/workspace-shell";
export { createDemoWorkspaceState, createEmptyWorkspaceState } from "./lib/initial-state";
export { mockSuggestedQuestions } from "./lib/mock-data";
export { isUsingMockApi } from "./api";
// Shared with other pages that call the backend.
export { useBackendStatus, type BackendStatus } from "./hooks/use-backend-status";
export { BackendStatusBanner } from "./components/backend-status-banner";
