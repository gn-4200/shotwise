"""Zip the human-direction record for an episode: script, prompts, breakdown, approvals, usage."""
import json
import zipfile
from pathlib import Path


def export(config, store, episode: str) -> Path:
    ep = config.episode_dir(episode)
    out = ep / "out"
    out.mkdir(parents=True, exist_ok=True)
    zpath = out / f"{episode}-evidence.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in [ep / "script.md", ep / "breakdown.json", ep / "breakdown" / "prompt.md"]:
            if p.exists():
                z.write(p, p.relative_to(ep).as_posix())
        for p in (ep / "shots").glob("*/prompts.json"):
            z.write(p, p.relative_to(ep).as_posix())
        z.writestr("approvals.json", json.dumps(store.list_approvals(episode), indent=2))
        z.writestr("usage.json", json.dumps(store.usage_summary(), indent=2))
        z.writestr("shots.json", json.dumps(store.list_shots(episode), indent=2, default=str))
    return zpath
