import os
import tempfile
from pathlib import Path

# Tests never touch the real database or real model/search credentials. The data dir lives
# under the repo (not /tmp) because Docker on macOS (colima, Docker Desktop) only shares $HOME.
_data = Path(__file__).resolve().parents[2] / "data"
_data.mkdir(exist_ok=True)
os.environ["BOUNCER_DATA_DIR"] = tempfile.mkdtemp(prefix="test-", dir=_data)
for key in ("NEBIUS_API_KEY", "TAVILY_API_KEY", "GITHUB_TOKEN"):
    os.environ[key] = ""
