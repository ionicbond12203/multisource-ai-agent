import { apiUrl } from "@/lib/api-url";
import { createHttpChatClient, createHttpIngestionClient } from "./http-clients";
import { mockChatClient, mockIngestionClient } from "./mock-clients";
import type { ChatClient, IngestionClient } from "./types";

export * from "./types";
export { apiUrl };

/**
 * Picks the real backend when NEXT_PUBLIC_API_URL is set (see .env.example),
 * otherwise the in-browser mocks.
 */
export const isUsingMockApi = !apiUrl;

export const chatClient: ChatClient = apiUrl ? createHttpChatClient(apiUrl) : mockChatClient;

export const ingestionClient: IngestionClient = apiUrl
  ? createHttpIngestionClient(apiUrl)
  : mockIngestionClient;
