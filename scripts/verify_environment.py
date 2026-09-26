from __future__ import annotations

import shutil
import subprocess
import sys


def command_version(command: str, args: list[str]) -> str | None:
    executable = shutil.which(command)
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return (result.stdout or result.stderr).strip().splitlines()[0]
    except OSError:
        return None


checks = {
    "Python": f"Python {sys.version.split()[0]}",
    "Node.js": command_version("node", ["--version"]),
    "npm": command_version("npm", ["--version"]),
    "Docker": command_version("docker", ["--version"]),
}

print("HEATSENSE AI environment verification")
print("-" * 42)
for name, value in checks.items():
    status = "PASS" if value else "FAIL"
    print(f"[{status}] {name}: {value or 'not found'}")

missing = [name for name, value in checks.items() if not value]
if missing:
    print("\\nMissing prerequisites:", ", ".join(missing))
    raise SystemExit(1)
