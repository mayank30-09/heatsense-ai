import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { loginAuth, getMeAuth, type TokenResponse } from "../authApi";
import { runInterventionOptimization } from "../interventionsApi";
import type { OptimizeRequestPayload } from "../../types/interventions";

describe("authApi and In-Memory Security Invariants", () => {
  const mockTokenResponse: TokenResponse = {
    access_token: "mock-valid-jwt-token-xyz",
    token_type: "Bearer",
    expires_in_minutes: 480,
    user: {
      id: "usr_pln_002",
      username: "planner_officer",
      email: "planner@surat.gov.in",
      role: "planner",
      is_active: true,
      department: "Town Planning Department, SMC",
    },
  };

  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("loginAuth", () => {
    it("login success: posts credentials and returns token and user", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTokenResponse,
      });

      const res = await loginAuth("planner_officer", "mock_password");

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, init] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/auth/login");
      expect(init.method).toBe("POST");
      expect(JSON.parse(init.body)).toEqual({
        username: "planner_officer",
        password: "mock_password",
      });
      expect(res.access_token).toBe("mock-valid-jwt-token-xyz");
      expect(res.user.role).toBe("planner");
    });

    it("login failure: 401 throws invalid username or password error", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(loginAuth("planner_officer", "wrong_pw")).rejects.toThrow(
        "Invalid username or password."
      );
    });

    it("login 429: throws rate limit throttling error with retry time", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: {
          get: (name: string) => (name === "Retry-After" ? "45" : null),
        },
        json: async () => ({
          detail: "Too many authentication attempts. Please try again in 45 seconds.",
        }),
      });

      await expect(loginAuth("planner_officer", "any_pw")).rejects.toThrow(
        "Too many authentication attempts. Please try again in 45 seconds."
      );
    });

    it("login 429: falls back to Retry-After header if body empty", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 429,
        headers: {
          get: (name: string) => (name === "Retry-After" ? "30" : null),
        },
        json: async () => {
          throw new Error("No JSON");
        },
      });

      await expect(loginAuth("planner_officer", "any_pw")).rejects.toThrow(
        "Too many authentication attempts. Please try again in 30 seconds."
      );
    });

    it("login failure: 403 throws account inactive error", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 403,
      });

      await expect(loginAuth("planner_officer", "any_pw")).rejects.toThrow(
        "Account is inactive. Contact the SMC system administrator."
      );
    });

    it("login network failure: handles network error gracefully", async () => {
      (fetch as any).mockRejectedValueOnce(new TypeError("Failed to fetch"));

      await expect(loginAuth("planner_officer", "any_pw")).rejects.toThrow(
        "Network error: Unable to connect to authentication server."
      );
    });
  });

  describe("storage untouched", () => {
    it("confirms browser localStorage and sessionStorage are never accessed or mutated", async () => {
      const mockStorage = {
        getItem: vi.fn(),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
        length: 0,
        key: vi.fn(),
      };
      vi.stubGlobal("localStorage", mockStorage);
      vi.stubGlobal("sessionStorage", mockStorage);

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTokenResponse,
      });

      // Execute login
      const res = await loginAuth("planner_officer", "mock_pw");
      expect(res.access_token).toBeDefined();

      // Invariants: Storage must remain completely untouched
      expect(mockStorage.setItem).not.toHaveBeenCalled();
      expect(mockStorage.getItem).not.toHaveBeenCalled();
      expect(mockStorage.removeItem).not.toHaveBeenCalled();
      expect(mockStorage.clear).not.toHaveBeenCalled();
    });
  });

  describe("header only when authenticated", () => {
    const payload: OptimizeRequestPayload = {
      budget_inr: 1000000,
      algorithm: "greedy",
      max_candidates: 10,
    };

    it("omits Authorization header when unauthenticated", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          algorithm: "GREEDY",
          budget_inr: 1000000,
          solutions_count: 0,
          solutions: [],
        }),
      });

      // Call without authToken
      await runInterventionOptimization(payload);

      expect(fetch).toHaveBeenCalledTimes(1);
      const [, init] = (fetch as any).mock.calls[0];
      expect(init.headers["Authorization"]).toBeUndefined();
      expect(init.headers["Content-Type"]).toBe("application/json");
    });

    it("includes Authorization Bearer header only when authenticated with valid token", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          algorithm: "GREEDY",
          budget_inr: 1000000,
          solutions_count: 1,
          solutions: [],
        }),
      });

      // Call with authToken
      await runInterventionOptimization(payload, "planner-jwt-token-abc");

      expect(fetch).toHaveBeenCalledTimes(1);
      const [, init] = (fetch as any).mock.calls[0];
      expect(init.headers["Authorization"]).toBe("Bearer planner-jwt-token-abc");
    });

    it("getMeAuth sends Authorization header with Bearer token", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockTokenResponse.user,
      });

      const user = await getMeAuth("valid-jwt-token-123");

      expect(fetch).toHaveBeenCalledTimes(1);
      const [url, init] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/auth/me");
      expect(init.headers["Authorization"]).toBe("Bearer valid-jwt-token-123");
      expect(user.username).toBe("planner_officer");
    });
  });

  describe("401 clears session behavior", () => {
    it("throws 401 session expired when getMe encounters expired credentials", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      await expect(getMeAuth("expired-token")).rejects.toThrow(
        "Session expired or invalid credentials (401)."
      );
    });

    it("optimization throws HTTP 401 which signals in-memory session clearance", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 401,
      });

      const payload: OptimizeRequestPayload = {
        budget_inr: 5000000,
        algorithm: "greedy",
      };

      await expect(
        runInterventionOptimization(payload, "stale-or-revoked-token")
      ).rejects.toThrow("Optimization failed: HTTP 401");
    });
  });
});
