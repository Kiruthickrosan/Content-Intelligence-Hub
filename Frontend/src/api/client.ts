const BASE = (import.meta.env["VITE_API_BASE_URL"] || "http://127.0.0.1:8000").replace(/\/$/, "");
const KEY = "youtube_qa_access_token";
export const tokenStore = {
  get: () => (typeof window === "undefined" ? null : sessionStorage.getItem(KEY)),
  set: (v: string) => sessionStorage.setItem(KEY, v),
  clear: () => sessionStorage.removeItem(KEY),
};
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function request<T>(path: string, init: RequestInit = {}, auth = true): Promise<T> {
  const h = new Headers(init.headers);
  if (
  init.body &&
  !h.has("Content-Type") &&
  !(init.body instanceof FormData) &&
  !(init.body instanceof URLSearchParams)
) {
  h.set("Content-Type", "application/json");
}
  const t = tokenStore.get();
  if (auth && t) h.set("Authorization", `Bearer ${t}`);
  let r: Response;
  try {
    r = await fetch(BASE + path, { ...init, headers: h });
  } catch {
    throw new ApiError("Unable to connect to the backend. Check that FastAPI is running.", 0);
  }
  const text = await r.text();
  let p: any;
  try {
    p = text ? JSON.parse(text) : undefined;
  } catch {
    p = text;
  }
  if (!r.ok) {
    if (r.status === 401 && auth) window.dispatchEvent(new Event("qa:unauthorized"));
    const d = p?.detail;
    throw new ApiError(
      Array.isArray(d) ? d.map((x: any) => x.msg).join(" · ") : d || `Request failed (${r.status})`,
      r.status,
    );
  }
  return p as T;
}
