import { AppHeader } from "@/components/app-header";
import {
  WorkspaceShell,
  createDemoWorkspaceState,
  createEmptyWorkspaceState,
  isUsingMockApi,
  mockSuggestedQuestions,
} from "@/features/workspace";

export default function WorkspacePage() {
  return (
    <>
      <AppHeader activeHref="/" apiMode={isUsingMockApi ? "mock" : "live"} />
      <WorkspaceShell
        // Without a backend, show the sample conversation; with one, start empty.
        initialState={isUsingMockApi ? createDemoWorkspaceState() : createEmptyWorkspaceState()}
        // Sample questions only make sense for the sample files.
        suggestedQuestions={isUsingMockApi ? mockSuggestedQuestions : []}
      />
    </>
  );
}
