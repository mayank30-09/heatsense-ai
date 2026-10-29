from pathlib import Path

p = Path("frontend/src/services/__tests__/interventionsApi.test.ts")
content = p.read_text(encoding="utf-8")

old_part = """      expect(res).toEqual(mockDetail);
    });
  });
})
  describe("Dynamic World Land Cover API", () => {"""

new_part = """      expect(res).toEqual(mockDetail);
    });
  });

  describe("Dynamic World Land Cover API", () => {"""

assert old_part in content, "old_part not found"
p.write_text(content.replace(old_part, new_part, 1), encoding="utf-8", newline="\n")
print("Fixed braces in interventionsApi.test.ts")

