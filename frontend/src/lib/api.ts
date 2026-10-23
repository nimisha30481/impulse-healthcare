/** Tiny fetch wrapper: same-origin cookies, CSRF header on writes, readable errors. */

export class ApiError extends Error {
  status: number;
  fields: Record<string, string>;
  constructor(status: number, message: string, fields: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.fields = fields;
  }
}

function csrfToken(): string | undefined {
  return document.cookie
    .split("; ")
    .find((c) => c.startsWith("impulse_csrf="))
    ?.split("=")[1];
}

const SERVER_DOWN = "DoseWISE can't reach its server right now. It restarts automatically, so please try again in a few seconds.";

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  const init: RequestInit = { method, credentials: "same-origin", headers };
  if (method !== "GET") {
    const t = csrfToken();
    if (t) headers["X-CSRF-Token"] = t;
  }
  if (body instanceof FormData) {
    init.body = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, SERVER_DOWN);
  }
  if (!res.ok) {
    // A bare 5xx with no JSON body means the dev proxy couldn't reach the backend (e.g. it is restarting).
    let msg = res.status >= 500 ? SERVER_DOWN : res.statusText || "Something went wrong";
    const fields: Record<string, string> = {};
    try {
      const data = await res.json();
      if (typeof data.detail === "string") msg = data.detail;
      for (const e of data.errors ?? []) fields[e.field.replace(/^body\./, "")] = e.message;
    } catch {
      /* non-JSON error */
    }
    if (res.status === 401 && !url.includes("/api/auth/")) {
      window.dispatchEvent(new CustomEvent("impulse:unauthorized"));
    }
    throw new ApiError(res.status, msg, fields);
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) return res.json();
  return (await res.blob()) as unknown as T;
}

export const api = {
  get: <T = any>(url: string) => request<T>("GET", url),
  post: <T = any>(url: string, body?: unknown) => request<T>("POST", url, body ?? {}),
  put: <T = any>(url: string, body?: unknown) => request<T>("PUT", url, body ?? {}),
  patch: <T = any>(url: string, body?: unknown) => request<T>("PATCH", url, body ?? {}),
  del: <T = any>(url: string) => request<T>("DELETE", url),
};

export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) return e.message;
  if (e instanceof Error) return e.message;
  return "Something went wrong";
}
