from pathlib import Path

import typer
from dotenv import load_dotenv

app = typer.Typer(help="Shotwise: AI story-series production pipeline", no_args_is_help=True, add_completion=False)


@app.callback()
def _init(ctx: typer.Context, root: Path = typer.Option(Path("."), "--root", help="project folder")):
    from shotwise.config import load_config
    from shotwise.store import make_store
    load_dotenv(root / ".env")
    cfg = load_config(root)
    ctx.obj = {"config": cfg, "store": make_store(cfg)}


@app.command("config-check")
def config_check(ctx: typer.Context):
    """Validate config, ping every enabled provider, print the effective chain per stage."""
    from shotwise.providers.registry import build
    cfg = ctx.obj["config"]
    for name, p in cfg.providers.items():
        if not p.enabled:
            health, detail = "-", "disabled"
        else:
            try:
                prov = build(name, p)
                health = "ok" if prov.healthcheck() else "down"
                detail = getattr(prov, "detail", "") or ("" if health == "ok" else "not reachable or key missing")
            except Exception as e:                                       # noqa: BLE001
                health, detail = "error", str(e)[:80]
        color = {"ok": "green", "down": "yellow", "error": "red"}.get(health)
        typer.secho(f"{name:18} {p.type:16} {health:6} {detail}", fg=color)
    typer.echo("")
    for stage, s in cfg.pipeline.stages.items():
        active = [n for n in s.chain if cfg.providers[n].enabled]
        typer.echo(f"stage {stage:10} chain={active or '-'}")


@app.command()
def script(ctx: typer.Context, episode: str, idea: str = typer.Option("", "--idea", help="episode idea; saved to idea.md"),
           provider: str = typer.Option(None, "--provider")):
    """Write episodes/<ep>/script.md from an idea via the LLM chain (or paste it on the manual lane)."""
    from shotwise.stages import script as st
    ep = ctx.obj["config"].episode_dir(episode)
    ep.mkdir(parents=True, exist_ok=True)
    if idea:
        (ep / "idea.md").write_text(idea, encoding="utf-8")
    _guard(lambda: st.run(ctx.obj["config"], ctx.obj["store"], episode, provider), lambda p: typer.echo(f"script: {p}"))


@app.command()
def breakdown(ctx: typer.Context, episode: str, provider: str = typer.Option(None, "--provider"),
              reload: bool = typer.Option(False, "--reload", help="re-sync the store after editing breakdown.json")):
    """Script to breakdown.json via the LLM chain (or the manual lane)."""
    from shotwise.stages import breakdown as st
    if reload:
        n = st.sync_store(ctx.obj["config"], ctx.obj["store"], st.load(ctx.obj["config"], episode))
        typer.echo(f"reloaded {n} shots")
        return
    _guard(lambda: st.run(ctx.obj["config"], ctx.obj["store"], episode, provider),
           lambda b: typer.echo(f"breakdown: {len(b.scenes)} scenes, {sum(len(s.shots) for s in b.scenes)} shots"))


@app.command()
def run(ctx: typer.Context, stage: str, episode: str, shots: str = typer.Option("", "--shots"),
        provider: str = typer.Option(None, "--provider")):
    """Run one stage: keyframes | video | voice | lipsync | music. --shots s01_01,s01_02 limits it."""
    from shotwise.stages.runner import STAGES, run_stage
    if stage not in STAGES:
        typer.secho(f"stage must be one of {STAGES}", fg="red")
        raise typer.Exit(2)
    _report(run_stage(ctx.obj["config"], ctx.obj["store"], stage, episode, shots.split(",") if shots else None, provider))


@app.command()
def resume(ctx: typer.Context, episode: str):
    """Collect manual and remote results, then continue every stage that has work."""
    from shotwise.stages.runner import resume as _resume
    _guard(lambda: _resume(ctx.obj["config"], ctx.obj["store"], episode), _report)


@app.command()
def review(ctx: typer.Context, port: int = 8787, host: str = "127.0.0.1"):
    """Open the local review page."""
    import uvicorn
    from shotwise.review.app import create_app
    typer.echo(f"review page: http://{host}:{port}")
    uvicorn.run(create_app(ctx.obj["config"], ctx.obj["store"]), host=host, port=port, log_level="warning")


@app.command()
def assemble(ctx: typer.Context, episode: str):
    """Render the master mp4 and srt (needs ffmpeg and pydub)."""
    from shotwise.stages import assemble as st
    typer.echo(f"master: {st.run(ctx.obj['config'], episode)}")


@app.command()
def cutdowns(ctx: typer.Context, episode: str):
    """Render the vertical clips from the master."""
    from shotwise.stages import cutdowns as st
    for p in st.run(ctx.obj["config"], episode):
        typer.echo(str(p))


@app.command()
def publish(ctx: typer.Context, episode: str, dry_run: bool = typer.Option(False, "--dry-run")):
    """Upload the master to YouTube as private, with the synthetic media disclosure."""
    from shotwise.stages import publish as st
    _guard(lambda: st.run(ctx.obj["config"], ctx.obj["store"], episode, dry_run),
           lambda r: typer.echo("\n".join(f"{k}: {v}" for k, v in r.items())))


@app.command()
def sync(ctx: typer.Context, push: bool = typer.Option(True), pull: bool = typer.Option(True)):
    """rclone the queue to and from the remote worker folder."""
    from shotwise import sync as s
    if push:
        s.push(ctx.obj["config"])
    if pull:
        s.pull(ctx.obj["config"])


@app.command()
def worker(ctx: typer.Context, once: bool = typer.Option(False, "--once"), comfy: str = typer.Option("${COMFY_URL}")):
    """Run the queue worker against the local ComfyUI."""
    import os
    from shotwise.workers.comfy_worker import serve
    cfg = ctx.obj["config"]
    url = os.environ.get("COMFY_URL", "http://127.0.0.1:8188") if comfy.startswith("$") else comfy
    serve(cfg.root / cfg.pipeline.workers.queue_dir, url, cfg.root / "workflows", once)


@app.command()
def usage(ctx: typer.Context, day: str = typer.Option(None, "--day", help="YYYY-MM-DD")):
    """Provider usage and cost ledger."""
    rows = ctx.obj["store"].usage_summary(day)
    typer.echo(f"{'provider':18} {'calls':>5} {'ok':>4} {'fail':>4} {'units':>9} {'usd':>7}")
    for r in rows:
        typer.echo(f"{r['provider']:18} {r['calls']:>5} {r['ok']:>4} {r['failed']:>4} {r['units']:>9.0f} {r['cost_usd']:>7.2f}")


@app.command()
def evidence(ctx: typer.Context, episode: str):
    """Zip the human-direction record for an episode."""
    from shotwise.stages.evidence import export
    typer.echo(str(export(ctx.obj["config"], ctx.obj["store"], episode)))


def _report(report: dict):
    for k, v in report.items():
        if v:
            typer.echo(f"{k:8} {len(v):4}  {', '.join(v[:12])}{' ...' if len(v) > 12 else ''}")
    if report.get("manual"):
        typer.secho("Manual steps are waiting: see the Manual page in `shotwise review`, then `shotwise resume`.", fg="yellow")


def _guard(fn, on_ok=None):
    from shotwise.chain import StageBlocked
    from shotwise.providers.base import ManualRequired
    try:
        out = fn()
    except ManualRequired as e:
        typer.secho(f"Manual step: open {e.request_file} and save the result as {e.expected_output}", fg="yellow")
        return
    except StageBlocked as e:
        typer.secho(str(e), fg="red")
        raise typer.Exit(2)
    if on_ok:
        on_ok(out)


if __name__ == "__main__":
    app()
