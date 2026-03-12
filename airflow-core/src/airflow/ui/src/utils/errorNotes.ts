import { OpenAPI } from "openapi/requests/core/OpenAPI";

const buildBaseUrl = () => {
  const base = OpenAPI.BASE ?? "";
  const normalizedBase = base.endsWith("/") ? base.slice(0, -1) : base;
  return normalizedBase;
};

const constructUrl = (path: string) => {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${buildBaseUrl()}${normalizedPath}`;
};

const defaultHeaders = {
  "Content-Type": "application/json",
  accept: "application/json",
};

const parseBody = async (response: Response) => {
  const text = await response.text();
  if (!text) {
    return undefined;
  }

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
};

const createApiError = (
  method: string,
  url: string,
  response: Response,
  body: unknown,
  requestBody?: unknown,
) => {
  const message =
    typeof body === "object" && body !== null && "detail" in (body as Record<string, unknown>)
      ? (body as Record<string, unknown>).detail ?? response.statusText
      : response.statusText;

  const error = new Error(message ?? "Request failed");

  Object.assign(error, {
    name: "ApiError",
    url,
    status: response.status,
    statusText: response.statusText,
    body,
    request: {
      method,
      url,
      body: requestBody,
    },
  });

  return error;
};

const handleResponse = async <T>(
  response: Response,
  method: string,
  url: string,
  requestBody?: unknown,
): Promise<T> => {
  const body = await parseBody(response);

  if (!response.ok) {
    throw createApiError(method, url, response, body, requestBody);
  }

  return (body as T) ?? (undefined as T);
};

const requestJson = async <T>(path: string, method: string, body?: unknown) => {
  const url = constructUrl(path);
  const response = await fetch(url, {
    method,
    credentials: OpenAPI.CREDENTIALS,
    headers: {
      ...defaultHeaders,
      ...(typeof OpenAPI.HEADERS === "object" && OpenAPI.HEADERS !== null ? OpenAPI.HEADERS : {}),
    },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(response, method, url, body);
};

export type ErrorNoteResponse = {
  note_id: number;
  signature_id: number;
  author: string;
  note_text: string;
  external_url?: string | null;
  created_at: string;
  updated_at: string;
};

export type ErrorNoteCollectionResponse = {
  notes: Array<ErrorNoteResponse>;
  total_entries: number;
};

export type ErrorNoteCreateBody = {
  highlighted_text: string;
  author: string;
  note_text: string;
  external_url?: string | null;
};

export const lookupErrorNotes = (highlighted_text: string) =>
  requestJson<ErrorNoteCollectionResponse>("/ui/error-notes/lookup", "POST", {
    highlighted_text,
  });

export const createErrorNote = (body: ErrorNoteCreateBody) =>
  requestJson<ErrorNoteResponse>("/ui/error-notes", "POST", body);
