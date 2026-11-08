/**
 * Base URL of the FastAPI backend, from NEXT_PUBLIC_API_URL, without a trailing slash.
 * Undefined when the variable is not set: the app then runs on built-in sample data.
 */
export const apiUrl = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || undefined;
