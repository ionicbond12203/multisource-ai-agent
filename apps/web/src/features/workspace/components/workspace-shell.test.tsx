import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { createDemoWorkspaceState } from "../lib/initial-state";
import { WorkspaceShell } from "./workspace-shell";

/**
 * End-to-end behaviour of the page against the built-in mock API
 * (NEXT_PUBLIC_API_URL is not set in tests).
 */
function renderWorkspace() {
  render(<WorkspaceShell initialState={createDemoWorkspaceState()} suggestedQuestions={[]} />);
  return userEvent.setup();
}

describe("WorkspaceShell", () => {
  it("shows the cited passage of the selected source", async () => {
    const user = renderWorkspace();
    const evidence = screen.getByRole("complementary", { name: "Evidence" });

    expect(within(evidence).getByText(/between 2 °C and 8 °C from depot to outlet/)).toBeInTheDocument();

    await user.click(screen.getAllByRole("button", { name: /^Source 2:/ })[0]);

    expect(within(evidence).getByText(/reported to Quality Assurance within 24 hours/)).toBeInTheDocument();
    expect(
      within(evidence).queryByText(/between 2 °C and 8 °C from depot to outlet/),
    ).not.toBeInTheDocument();
  });

  it("sends a question with Enter and shows the answer", async () => {
    const user = renderWorkspace();
    await user.type(screen.getByLabelText("Ask a question"), "What is form QA-07?{Enter}");

    expect(screen.getByText("What is form QA-07?")).toBeInTheDocument();
    expect(screen.getByText(/Searching your files/)).toBeInTheDocument();
    // The demo answer is already grounded; wait for a second one.
    await waitFor(() => expect(screen.getAllByText(/Grounded · every claim cited/)).toHaveLength(2), {
      timeout: 3000,
    });
  });

  it("says nothing was found when every file is switched off", async () => {
    const user = renderWorkspace();
    await user.click(screen.getByRole("checkbox", { name: "Use SOP_Cold_Chain_v3.pdf in answers" }));
    await user.click(screen.getByRole("checkbox", { name: "Use Halal_QA_Manual_2026.pdf in answers" }));
    expect(screen.getByText("Answering from 0 of 4 files")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Ask a question"), "Anything?{Enter}");
    expect(await screen.findByText("Not found in your files", {}, { timeout: 3000 })).toBeInTheDocument();
  });

  it("does not send an empty question", async () => {
    const user = renderWorkspace();
    await user.type(screen.getByLabelText("Ask a question"), "   ");
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
  });
});
