from shotwise.chain import run_chain
from shotwise.providers.base import Job
from shotwise.providers.registry import chain_for
from shotwise.stages import breakdown as bd
from shotwise.stages.assemble import timeline


def metadata(config, episode: str) -> dict:
    breakdown = bd.load(config, episode)
    p = config.pipeline.stages["publish"].params
    chapters, seen = [], set()
    for shot, start in timeline(breakdown):
        if shot["scene"] not in seen:
            seen.add(shot["scene"])
            title = next(s.title for s in breakdown.scenes if s.id == shot["scene"])
            chapters.append(f"{int(start) // 60:02}:{int(start) % 60:02} {title}")
    description = (f"{breakdown.logline}\n\nChapters\n" + "\n".join(chapters) +
                   "\n\nMade with AI tools under human direction: original script, storyboard and every shot approved by the creator.")
    return {"title": f"{episode.replace('-', ' ').title()}: {breakdown.logline[:60]}", "description": description,
            "tags": ["animated series", "AI animation", "story"], "privacy": p.get("privacy", "private"),
            "synthetic_media": p.get("synthetic_media", True), "playlist_id": p.get("playlist_id")}


def run(config, store, episode: str, dry_run: bool = False) -> dict:
    meta = metadata(config, episode)
    master = config.episode_dir(episode) / "out" / f"{episode}.mp4"
    if dry_run:
        return meta | {"video": str(master), "exists": master.exists()}
    if not master.exists():
        raise RuntimeError(f"master not found, run `shotwise assemble {episode}` first")
    job = Job("publish", episode, None, config.episode_dir(episode) / "out", inputs={"video": master}, params=meta)
    result = run_chain(chain_for(config, "publish"), job, store)
    store.record_approval(episode, "-", "publish", "uploaded", result.data.get("url", ""))
    return result.data
