"""Script stage: an episode idea plus the bible becomes episodes/<ep>/script.md through the LLM chain."""
from jinja2 import Template

from shotwise.chain import run_chain
from shotwise.providers.base import Job
from shotwise.providers.registry import chain_for


def run(config, store, episode: str, force: str | None = None):
    ep = config.episode_dir(episode)
    idea = (ep / "idea.md").read_text(encoding="utf-8") if (ep / "idea.md").exists() else f"Episode {episode}"
    stage = config.pipeline.stages["script"]
    prompt = Template((config.root / "prompts" / "script.md").read_text(encoding="utf-8")).render(
        episode=episode, idea=idea, bible=config.bible()["text"], **{"target_minutes": 4, **stage.params})
    job = Job("script", episode, None, ep / "script_gen", prompt)          # no schema: manual lane expects response.md
    job.workdir.mkdir(parents=True, exist_ok=True)
    (job.workdir / "prompt.md").write_text(prompt, encoding="utf-8")
    result = run_chain(chain_for(config, "script", force), job, store, attempts=stage.attempts)
    out = ep / "script.md"
    out.write_text(result.data["text"].strip() + "\n", encoding="utf-8")
    return out
