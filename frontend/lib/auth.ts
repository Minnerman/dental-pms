export const TOKEN_KEY = "dental_pms_token";

function setTokenCookie(token: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
}

function clearTokenCookie() {
  if (typeof document === "undefined") return;
  document.cookie = `${TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  window.localStorage.setItem(TOKEN_KEY, token);
  setTokenCookie(token);
}

export function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY);
  clearTokenCookie();
}

export async function apiFetch(path: string, init: RequestInit = {}) {
  const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? "/api").replace(/\/$/, "");
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const url = path.startsWith("http")
    ? path
    : apiBase && (normalizedPath === apiBase || normalizedPath.startsWith(`${apiBase}/`))
      ? normalizedPath
      : `${apiBase}${normalizedPath}`;
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  headers.set("Content-Type", "application/json");
  return fetch(url, { ...init, headers });
}

export type LoginResponse = {
  accessToken: string;
  mustChangePassword: boolean;
};

function normaliseLoginResponse(data: unknown): LoginResponse {
  const record = (data ?? {}) as Record<string, unknown>;
  const accessToken =
    (record.access_token as string | undefined) ||
    (record.accessToken as string | undefined) ||
    "";
  const mustChangePassword = Boolean(
    record.must_change_password ?? record.mustChangePassword
  );

  if (!accessToken) {
    const keys = Object.keys(record);
    throw new Error(
      `Login succeeded but token missing. Keys: ${keys.length ? keys.join(", ") : "none"}`
    );
  }

  return { accessToken, mustChangePassword };
}

export async function login(email: string, password: string): Promise<LoginResponse> {
  const base = (process.env.NEXT_PUBLIC_API_BASE ?? "/api").replace(/\/$/, "");
  const url = `${base}/auth/login`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    // ignore non-JSON responses
  }

  if (!res.ok) {
    const record = (data ?? {}) as Record<string, unknown>;
    const detail =
      (record.detail as string | undefined) ||
      (record.message as string | undefined) ||
      `HTTP ${res.status}`;
    throw new Error(detail);
  }

  return normaliseLoginResponse(data);
}
