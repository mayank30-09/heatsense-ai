import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_BASE_URL, getHealth } from "../api";

describe("api service", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe("API_BASE_URL", () => {
    it("is defined and defaults to local v1 api URL", () => {
      expect(API_BASE_URL).toBeDefined();
      expect(typeof API_BASE_URL).toBe("string");
      expect(API_BASE_URL).toContain("/api/v1");
    });
  });

  describe("getHealth", () => {
    it("fetches health endpoint and returns parsed json", async () => {
      const mockHealth = {
        status: "healthy",
        service: "heatsense-backend",
        database: "connected",
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockHealth,
      });

      const result = await getHealth();

      expect(fetch).toHaveBeenCalledTimes(1);
      const callUrl = (fetch as any).mock.calls[0][0];
      expect(callUrl).toBe(`${API_BASE_URL}/health`);
      expect(result).toEqual(mockHealth);
    });

    it("throws when health response is not ok", async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
      });

      await expect(getHealth()).rejects.toThrow("Health request failed: 500");
    });
  });
});
