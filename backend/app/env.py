import os
from pathlib import Path


def load_env_file() -> None:
    env_paths = [
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        Path(__file__).resolve().parents[1] / ".env",
    ]

    for env_path in env_paths:
        if env_path.exists():
            _load_env_path(env_path)


def _load_env_path(env_path: Path) -> None:
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
