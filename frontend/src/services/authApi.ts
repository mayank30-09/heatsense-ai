import { API_BASE_URL } from "./api";

export type UserRole = "public" | "planner" | "researcher" | "admin";

export interface AuthUser {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  department?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: AuthUser;
}

export async function loginAuth(
  username: string,
  password: string,
  signal?: AbortSignal
): Promise<TokenResponse> {
  const url = `${API_BASE_URL}/auth/login`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      throw err;
    }
    throw new Error("Network error: Unable to connect to authentication server.");
  }

  if (response.status === 401) {
    let detailMsg = "Invalid username or password.";
    try {
      const data = await response.json();
      if (data?.detail) detailMsg = data.detail;
    } catch {
      // fallback to default
    }
    throw new Error(detailMsg);
  }
  if (response.status === 429) {
    const retryAfter = response.headers?.get ? response.headers.get("Retry-After") : null;
    let detailMsg = "";
    try {
      const data = await response.json();
      if (data?.detail) detailMsg = data.detail;
    } catch {
      // fallback to header
    }
    const msg =
      detailMsg ||
      (retryAfter
        ? `Too many authentication attempts. Please try again in ${retryAfter} seconds.`
        : "Too many authentication attempts. Please try again later.");
    throw new Error(msg);
  }
  if (response.status === 403) {
    let detailMsg = "Account is inactive. Contact the SMC system administrator.";
    try {
      const data = await response.json();
      if (data?.detail) detailMsg = data.detail;
    } catch {
      // fallback to default
    }
    throw new Error(detailMsg);
  }
  if (!response.ok) {
    throw new Error(`Authentication failed: HTTP ${response.status}`);
  }

  return response.json() as Promise<TokenResponse>;
}

export async function getMeAuth(
  token: string,
  signal?: AbortSignal
): Promise<AuthUser> {
  const url = `${API_BASE_URL}/auth/me`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${token}`,
      },
      signal,
    });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      throw err;
    }
    throw new Error("Network error: Unable to connect to authentication server.");
  }

  if (response.status === 401) {
    let detailMsg = "Session expired or invalid credentials (401).";
    try {
      const data = await response.json();
      if (data?.detail) detailMsg = data.detail;
    } catch {
      // fallback to default
    }
    throw new Error(detailMsg);
  }
  if (response.status === 403) {
    let detailMsg = "Access forbidden (403).";
    try {
      const data = await response.json();
      if (data?.detail) detailMsg = data.detail;
    } catch {
      // fallback to default
    }
    throw new Error(detailMsg);
  }
  if (!response.ok) {
    throw new Error(`Profile check failed: HTTP ${response.status}`);
  }

  return response.json() as Promise<AuthUser>;
}
