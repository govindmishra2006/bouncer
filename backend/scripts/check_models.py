"""Day-1 check from the plan: confirm the Nemotron model IDs on Token Factory and make one call each.

Usage: NEBIUS_API_KEY=... .venv/bin/python scripts/check_models.py
Prints the Nemotron models the key can see and the latency/tokens of one tiny call per tier.
"""
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai import AsyncOpenAI  # noqa: E402

from bouncer.config import settings  # noqa: E402


async def main() -> int:
    if not settings.nebius_api_key:
        print("NEBIUS_API_KEY is not set (put it in .env or the environment).")
        return 2
    client = AsyncOpenAI(api_key=settings.nebius_api_key, base_url=settings.nebius_base_url)
    models = [m.id async for m in client.models.list()]
    nemotron = sorted(m for m in models if "nemotron" in m.lower())
    print(f"{len(models)} models visible; Nemotron models:\n  " + "\n  ".join(nemotron or ["(none)"]))
    rc = 0
    for tier, cfg in settings.tiers.items():
        if cfg.model_id not in models:
            print(f"[{tier}] {cfg.model_id}: NOT in the catalogue -> set NEMOTRON_{tier.upper()}_MODEL")
            rc = 1
            continue
        t = time.perf_counter()
        resp = await client.chat.completions.create(
            model=cfg.model_id, messages=[{"role": "user", "content": 'Reply with the JSON {"ok": true}.'}], max_tokens=200
        )
        print(f"[{tier}] {cfg.model_id}: {int((time.perf_counter() - t) * 1000)} ms, "
              f"{resp.usage.prompt_tokens}+{resp.usage.completion_tokens} tokens -> {resp.choices[0].message.content!r:.80}")
    return rc


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
