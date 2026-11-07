import type { AssistantMessage, KnowledgeFile, UserMessage } from "../types";

/**
 * Sample data used until the backend is connected (see lib/chat-client.ts).
 * All content describes a FICTIONAL beverage distributor; it is not real
 * company policy.
 */

export const mockFiles: KnowledgeFile[] = [
  {
    id: "file_sop",
    remoteId: "file_sop",
    name: "SOP_Cold_Chain_v3.pdf",
    sizeBytes: 1_840_000,
    status: { kind: "ready", pages: 18, chunks: 52 },
    enabled: true,
  },
  {
    id: "file_halal",
    remoteId: "file_halal",
    name: "Halal_QA_Manual_2026.pdf",
    sizeBytes: 4_120_000,
    status: { kind: "ready", pages: 42, chunks: 118 },
    enabled: true,
  },
  {
    id: "file_policy",
    remoteId: "file_policy",
    name: "Distributor_Policy.docx",
    sizeBytes: 2_400_000,
    status: { kind: "processing", stage: "embedding", progress: 0.64 },
    enabled: true,
  },
  {
    id: "file_scan",
    remoteId: "file_scan",
    name: "scanned_invoice.pdf",
    sizeBytes: 3_050_000,
    status: { kind: "failed", reason: "No text layer found", recovery: "ocr" },
    enabled: false,
  },
];

export const mockQuestion: UserMessage = {
  id: "msg_q1",
  role: "user",
  content:
    "What temperature must chilled RTD tea be kept at during last-mile delivery, and what do drivers do if it goes out of range?",
};

export const mockAnswer: AssistantMessage = {
  id: "msg_a1",
  role: "assistant",
  content: [
    "Chilled RTD tea must stay between **2 °C and 8 °C** from depot to outlet, and the in-truck logger must record at least every 5 minutes [1].",
    "",
    "If the product is above 8 °C for more than 30 minutes, the driver should:",
    "",
    "1. Stop the delivery and tag the pallet “On hold – temperature” [1]",
    "2. Report to QA within 24 hours using form QA-07 [2]",
    "3. Keep the logger file with the batch record for traceability [3]",
  ].join("\n"),
  grounded: true,
  followUps: ["Show form QA-07 fields", "How many excursions happened in Q3?"],
  run: {
    totalMs: 3800,
    steps: [
      { id: "s1", node: "router", summary: "Document question → RAG path", durationMs: 400, status: "done" },
      {
        id: "s2",
        node: "retrieve",
        summary: "Hybrid search · top-k 8 · 2 files",
        durationMs: 900,
        status: "done",
      },
      {
        id: "s3",
        node: "grade",
        summary: "6 of 8 chunks relevant, 2 dropped",
        durationMs: 600,
        status: "done",
      },
      { id: "s4", node: "generate", summary: "Answer with 3 citations", durationMs: 1900, status: "done" },
    ],
  },
  sources: [
    {
      index: 1,
      fileId: "file_sop",
      fileName: "SOP_Cold_Chain_v3.pdf",
      location: "Section 4.2 · page 7 of 18",
      heading: "4.2 Last-mile temperature control",
      score: 0.91,
      passages: [
        {
          text: "Vehicles carrying chilled ready-to-drink products must be pre-cooled before loading and fitted with a calibrated data logger.",
          cited: false,
        },
        {
          text: "Product temperature shall be maintained between 2 °C and 8 °C from depot to outlet. Loggers record at intervals not exceeding five minutes.",
          cited: true,
        },
        {
          text: "Where the product exceeds 8 °C for more than 30 minutes, the consignment is placed on hold and tagged accordingly.",
          cited: true,
        },
        { text: "Door-open time at each outlet should be kept as short as practical.", cited: false },
      ],
    },
    {
      index: 2,
      fileId: "file_halal",
      fileName: "Halal_QA_Manual_2026.pdf",
      location: "Form QA-07 · page 31",
      heading: "Appendix C – Deviation reporting",
      score: 0.84,
      passages: [
        {
          text: "Any temperature deviation affecting finished goods is reported to Quality Assurance within 24 hours using form QA-07.",
          cited: true,
        },
      ],
    },
    {
      index: 3,
      fileId: "file_sop",
      fileName: "SOP_Cold_Chain_v3.pdf",
      location: "Section 6.1 · page 12",
      heading: "6.1 Records and traceability",
      score: 0.79,
      passages: [
        {
          text: "Logger files are attached to the batch record and retained for the period stated in the records policy.",
          cited: true,
        },
      ],
    },
  ],
};

export const mockSuggestedQuestions = [
  "What temperature must chilled RTD tea be kept at?",
  "Summarise the halal audit checklist",
  "What happens after a temperature excursion?",
];
