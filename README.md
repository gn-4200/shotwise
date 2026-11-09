# Shotwise

Config-driven production pipeline for AI story series: script to breakdown to keyframes to video to voice to episode to YouTube.
Every API or model is a provider in `config/providers.yaml`, every stage has a fallback chain in `config/pipeline.yaml`,
and the last link of every chain is a manual provider, so you can paste text or drop a file in and keep going.

Full plan: `docs/AI-Series-Studio-Plan.pdf`.

## Quick start (Windows)

```
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env            # then paste GEMINI_API_KEY (free tier, no billing)
shotwise config-check
shotwise breakdown ep00-pilot     # Gemini, or the manual lane if no key is set
shotwise review                   # http://127.0.0.1:8787
```

## Producing an episode

```
write episodes/<ep>/script.md
shotwise breakdown <ep>              -> edit episodes/<ep>/breakdown.json if needed
shotwise run keyframes <ep>          -> approve in the review page
shotwise run video <ep>              -> worker (local GPU or Kaggle) -> shotwise resume <ep>
shotwise run voice <ep> ; shotwise run lipsync <ep> ; shotwise run music <ep>
shotwise assemble <ep> ; shotwise cutdowns <ep>
shotwise publish <ep> --dry-run ; shotwise publish <ep>
shotwise evidence <ep>
```

Manual steps show up on the review page under Manual and as `MANUAL_*.md` files next to the expected output.
Finish them, then `shotwise resume <ep>`.

## Status

Work in progress.

- Working: configuration and validation, script breakdown into scenes and shots, the stage runner with
  provider fallback chains and manual lanes, the job queue, the local review page, and the test suite.
- Not done yet: no episode has been rendered end to end. The keyframe, video, voice and publish providers
  are written but have not been run against real models on a GPU.

## Tests

```
pip install -e ".[dev]"
pytest
```

The tests use their own cast (`tests/fixtures/cast.yaml`), so they do not depend on the story in `bible/`.
