# Feedback log (Token Factory, Nebius, Nemotron)

Required for the submission's feedback section. Entries below are only what was actually observed; fill in the live-call rows once a key is available (`make check-models` prints latency and token counts per tier).

## 2026-10-23: build day 1

**Nebius Token Factory**
- Used for: all model calls (OpenAI-compatible endpoint `https://api.tokenfactory.nebius.com/v1/`).
- Onboarding: the public quickstart gives the base URL and `NEBIUS_API_KEY` convention clearly. It does not say whether `response_format` (`json_object` / `json_schema`) is supported, so the gateway tries JSON mode and falls back. A structured-output page would help.
- Model catalogue: we could not find a public, unauthenticated list of exact model IDs. The Nemotron 3 IDs used here (`nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B`, `nvidia/nemotron-3-super-120b-a12b`, `nvidia/Nemotron-3-Ultra-550b-a55b`) come from third-party catalogue mirrors, with inconsistent capitalisation between sources. A public model page with copyable IDs would remove guesswork.
- Live calls: not yet made (no key in the build environment). TODO: time from sign-up to first call, latency per tier, structured-output reliability.

**Nebius Serverless Jobs**
- Considered for: one sandbox per reproduction.
- What we found in the CLI reference (`nebius ai job create`): no flag to disable outbound networking, a minimum timeout of 1 h, and defaults to GPU platforms. For short, untrusted, CPU-only, network-less runs, we used the plan's fallback: Docker `--network none` (deployable on a Nebius VM). A "no egress" option and CPU presets with second-level timeouts would make Jobs a natural fit for sandboxing.

**Nemotron 3 Nano / Super / Ultra**
- Planned roles: Nano for extraction, duplicates and failure summaries; Super for repro scripts and patches; Ultra for root cause and judgement-call explanations.
- Observations: TODO after first live run (JSON adherence, `<think>` output handling, patch quality on bug A).

**Would we build with it again?** TODO after the live run.
