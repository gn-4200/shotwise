import json

import yaml
from jinja2 import Template

from shotwise.chain import run_chain
from shotwise.providers.base import Job
from shotwise.providers.registry import chain_for
from shotwise.schemas import BREAKDOWN_SCHEMA, Breakdown


def load(config, episode: str) -> Breakdown:
    return Breakdown.model_validate_json((config.episode_dir(episode) / "breakdown.json").read_text(encoding="utf-8"))


def sync_store(config, store, breakdown: Breakdown) -> int:
    """Write every shot of the breakdown into the store and its shot folder. Returns the shot count."""
    n = 0
    for scene in breakdown.scenes:
        for shot in scene.shots:
            store.upsert_shot(breakdown.episode, shot.model_dump(), scene.id)
            sd = config.shot_dir(breakdown.episode, shot.id)
            sd.mkdir(parents=True, exist_ok=True)
            (sd / "shot.json").write_text(shot.model_dump_json(indent=2), encoding="utf-8")
            n += 1
    return n


def run(config, store, episode: str, force: str | None = None) -> Breakdown:
    ep = config.episode_dir(episode)
    script = (ep / "script.md").read_text(encoding="utf-8")
    bible = config.bible()
    stage = config.pipeline.stages["breakdown"]
    prompt = Template((config.root / "prompts" / "breakdown.md").read_text(encoding="utf-8")).render(
        episode=episode, script=script, bible=bible["text"], style=yaml.safe_dump(bible["style"]), **stage.params)
    job = Job("breakdown", episode, None, ep / "breakdown", prompt, schema=BREAKDOWN_SCHEMA)
    job.workdir.mkdir(parents=True, exist_ok=True)
    (job.workdir / "prompt.md").write_text(prompt, encoding="utf-8")       # evidence and reproducibility
    result = run_chain(chain_for(config, "breakdown", force), job, store, attempts=stage.attempts)
    data = dict(result.data or {})
    data["episode"] = episode
    breakdown = Breakdown.model_validate(data)                              # fails loudly if the model drifted
    (ep / "breakdown.json").write_text(breakdown.model_dump_json(indent=2), encoding="utf-8")
    sync_store(config, store, breakdown)
    return breakdown
