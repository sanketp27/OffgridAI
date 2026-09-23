import { API_CONFIG } from "@/config/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit & { parse?: (data: unknown) => T },
): Promise<T> {
  const url = `${API_CONFIG.baseUrl.replace(/\/$/, "")}${path}`;
  const res = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  const text = await res.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text) as unknown;
    } catch {
      json = text;
    }
  }

  if (!res.ok) {
    throw new ApiError(
      typeof json === "object" && json && "detail" in json
        ? String((json as { detail: unknown }).detail)
        : `Request failed (${res.status})`,
      res.status,
      json,
    );
  }

  if (init?.parse) return init.parse(json);
  return json as T;
}

export function createId(prefix: string) {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function delay(ms = 450) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}
