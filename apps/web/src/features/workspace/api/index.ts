import { createHttpChatClient, createHttpIngestionClient } from "./http-clients";
import { mockChatClient, mockIngestionClient } from "./mock-clients";
import type { ChatClient, IngestionClient } from "./types";

export * from "./types";

/**
 * Picks the real backend when NEXT_PUBLIC_API_URL is set (see .env.example),
 * otherwise the in-browser mocks.
 */
/** Backend base URL from NEXT_PUBLIC_API_URL, without a trailing slash; undefined in sample-data mode. */
export const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "");

export const isUsingMockApi = !apiUrl;

export const chatClient: ChatClient = apiUrl ? createHttpChatClient(apiUrl) : mockChatClient;

export const ingestionClient: IngestionClient = apiUrl
  ? createHttpIngestionClient(apiUrl)
  : mockIngestionClient;
