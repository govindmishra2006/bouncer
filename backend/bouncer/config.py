"""Runtime configuration, read once from environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load_dotenv() -> None:
    """Loads KEY=VALUE pairs from the repo's .env without overriding the environment."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for raw in env_file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class ModelTier:
    tier: str
    model_id: str
    usd_per_m_input: float
    usd_per_m_output: float


@dataclass(frozen=True)
class Settings:
    nebius_api_key: str = field(default_factory=lambda: _env("NEBIUS_API_KEY"))
    nebius_base_url: str = field(
        default_factory=lambda: _env("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    )
    tavily_api_key: str = field(default_factory=lambda: _env("TAVILY_API_KEY"))
    github_token: str = field(default_factory=lambda: _env("GITHUB_TOKEN"))
    github_repo: str = field(default_factory=lambda: _env("GITHUB_REPO"))
    data_dir: Path = field(default_factory=lambda: Path(_env("BOUNCER_DATA_DIR", str(ROOT / "data"))))
    sandbox_image: str = field(default_factory=lambda: _env("BOUNCER_SANDBOX_IMAGE", "bouncer-sandbox:1"))
    sandbox_timeout_s: int = field(default_factory=lambda: int(_env("BOUNCER_SANDBOX_TIMEOUT", "120")))
    model_timeout_s: float = field(default_factory=lambda: float(_env("BOUNCER_MODEL_TIMEOUT", "90")))
    daily_budget_usd: float = field(default_factory=lambda: float(_env("BOUNCER_DAILY_BUDGET_USD", "5")))
    hours_per_report: float = field(default_factory=lambda: float(_env("BOUNCER_HOURS_PER_REPORT", "1")))
    cve_lookup: bool = field(default_factory=lambda: _env("BOUNCER_CVE_LOOKUP", "1") != "0")

    @property
    def tiers(self) -> dict[str, ModelTier]:
        # Prices are the Token Factory list prices at time of writing (USD per 1M tokens);
        # override with env vars if they change. Model IDs are overridable for the same reason.
        return {
            "nano": ModelTier(
                "nano",
                _env("NEMOTRON_NANO_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
                float(_env("NEMOTRON_NANO_PRICE_IN", "0.06")),
                float(_env("NEMOTRON_NANO_PRICE_OUT", "0.24")),
            ),
            "super": ModelTier(
                "super",
                _env("NEMOTRON_SUPER_MODEL", "nvidia/nemotron-3-super-120b-a12b"),
                float(_env("NEMOTRON_SUPER_PRICE_IN", "0.30")),
                float(_env("NEMOTRON_SUPER_PRICE_OUT", "0.90")),
            ),
            "ultra": ModelTier(
                "ultra",
                _env("NEMOTRON_ULTRA_MODEL", "nvidia/Nemotron-3-Ultra-550b-a55b"),
                float(_env("NEMOTRON_ULTRA_PRICE_IN", "1.00")),
                float(_env("NEMOTRON_ULTRA_PRICE_OUT", "3.00")),
            ),
        }

    @property
    def models_live(self) -> bool:
        return bool(self.nebius_api_key)

    @property
    def repos_dir(self) -> Path:
        return self.data_dir / "repos"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "bouncer.sqlite3"


settings = Settings()
