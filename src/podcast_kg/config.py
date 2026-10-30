from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    api_key: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        raw_key = os.environ.get("PODCAST_KG_API_KEY")
        return cls(
            data_dir=Path(os.environ.get("PODCAST_KG_DATA_DIR", "/data")),
            api_key=raw_key if raw_key else None,
        )

    @property
    def db_path(self) -> Path:
        return self.data_dir / "podcast-kg.sqlite3"

    @property
    def graph_path(self) -> Path:
        return self.data_dir / "podcast.nq"

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
