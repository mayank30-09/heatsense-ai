from pathlib import Path

p = Path("frontend/src/services/__tests__/interventionsApi.test.ts")
content = p.read_text(encoding="utf-8")

# Add imports
if "fetchCellLandCover" not in content:
    content = content.replace(
        "  fetchClusterCells,\n",
        "  fetchClusterCells,\n  fetchCellLandCover,\n  fetchLandCoverSummary,\n",
        1
    )

new_tests = """
  describe("Dynamic World Land Cover API", () => {
    it("fetches cell land cover with 9-class probabilities and suitability", async () => {
      const mockDw = {
        cell_id: "R000_C249",
        top_class: "built",
        confidence: 0.6346,
        probabilities: { built: 0.6346, bare: 0.0396 },
        suitability: { rule_fired: "RULE_DW_BUILT_DENSE" },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockDw,
      });

      const res = await fetchCellLandCover("R000_C249", "summer", 2024);
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/landcover/R000_C249?season=summer&year=2024");
      expect(res).toEqual(mockDw);
    });

    it("fetches land cover summary", async () => {
      const mockSummary = {
        total_cells_recorded: 330,
        cells_sufficient: 330,
        class_distribution: { built: 302 },
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => mockSummary,
      });

      const res = await fetchLandCoverSummary("summer", 2024);
      expect(fetch).toHaveBeenCalledTimes(1);
      const [url] = (fetch as any).mock.calls[0];
      expect(url).toContain("/api/v1/interventions/landcover/summary?season=summer&year=2024");
      expect(res).toEqual(mockSummary);
    });
  });
});
"""

if "Dynamic World Land Cover API" not in content:
    content = content[:-4] + new_tests
    p.write_text(content, encoding="utf-8", newline="\n")
    print("Added Dynamic World tests to interventionsApi.test.ts")

