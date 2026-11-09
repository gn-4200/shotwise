"""Local review page: FastAPI + Jinja2 + HTMX. Approve, reject, manual lane, usage, providers."""
import json
import os
import re
import shutil
import threading
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from shotwise.providers.manual import request_name

STAGES = ("keyframes", "video", "voice", "lipsync", "music")
STAGE_DIRS = {"keyframes": "keyframes", "video": "video", "voice": "voice", "lipsync": "lipsync"}
VIEWABLE = {"keyframes": "cand_*.png", "video": "attempt_*.mp4", "lipsync": "attempt_*.mp4", "voice": "line_*.wav"}
_TYPE_LABELS = {
    "llm.gemini": "Google Gemini (text)", "llm.anthropic": "Anthropic Claude (text)", "llm.openai": "OpenAI or compatible (text)",
    "image.comfyui": "ComfyUI image workflow", "video.comfyui": "ComfyUI video workflow", "lipsync.comfyui": "ComfyUI lip-sync workflow",
    "music.comfyui": "ComfyUI music workflow", "tts.chatterbox": "Chatterbox voices (local)", "tts.kokoro": "Kokoro voices (local)",
    "publish.youtube": "YouTube upload",
}


def create_app(config, store) -> FastAPI:
    app = FastAPI(title="Shotwise review")
    base = Path(os.environ.get("SHOTWISE_UI_DIR") or Path(__file__).parent)   # alternate UI folder for theming
    app.mount("/static", StaticFiles(directory=base / "static"), name="static")
    (config.root / "episodes").mkdir(exist_ok=True)
    app.mount("/media", StaticFiles(directory=config.root / "episodes"), name="media")
    templates = Jinja2Templates(directory=base / "templates")
    jobs: dict[str, str] = {}                                    # background runs: key -> state

    def render(request, name, **ctx):
        ctx.update(episodes=store.list_episodes() or _episodes_on_disk(), backend=config.pipeline.storage.backend,
                   stages=STAGES, msg=request.query_params.get("msg", ""))
        return templates.TemplateResponse(request=request, name=name, context=ctx)

    def _episodes_on_disk():
        return sorted(p.name for p in (config.root / "episodes").iterdir()
                      if (p / "script.md").exists() or (p / "idea.md").exists())

    # ---------- config editing (settings page) ----------
    def _cfg_path(stem):
        for ext in (".json", ".yaml", ".yml"):
            if (config.root / "config" / f"{stem}{ext}").exists():
                return config.root / "config" / f"{stem}{ext}"
        raise FileNotFoundError(stem)

    def _read_cfg(stem):
        p = _cfg_path(stem)
        if p.suffix == ".json":
            return json.loads(p.read_text(encoding="utf-8"))
        import yaml
        return yaml.safe_load(p.read_text(encoding="utf-8"))

    def _write_cfg(stem, data):
        p = _cfg_path(stem)
        if p.suffix != ".json":                                  # settings are written as JSON from here on
            p.unlink()
            p = p.with_suffix(".json")
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _reload():
        nonlocal config, store
        from shotwise.config import load_config
        from shotwise.store import make_store
        config = load_config(config.root)
        store = make_store(config)

    def _set_env(key, value):
        env = config.root / ".env"
        lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
        lines = [ln for ln in lines if not ln.startswith(key + "=")] + [f"{key}={value}"]
        env.write_text("\n".join(lines) + "\n", encoding="utf-8")
        os.environ[key] = value

    def shots_of(ep):
        rows = store.list_shots(ep)
        return [s for s in rows if not s["id"].startswith("music:")], [s for s in rows if s["id"].startswith("music:")]

    def stage_stats(shots):
        stats = {}
        for st in STAGES:
            c = {}
            for s in shots:
                k = s["stages"].get(st, {}).get("status", "pending")
                c[k] = c.get(k, 0) + 1
            done = c.get("approved", 0) + c.get("done", 0) + c.get("skipped", 0)
            stats[st] = {"counts": c, "done": done, "pct": int(100 * done / len(shots)) if shots else 0}
        return stats

    def background(key, fn):
        if jobs.get(key) == "running":
            return False
        jobs[key] = "running"

        def wrap():
            try:
                fn()
                jobs[key] = "finished"
            except Exception as e:                                # noqa: BLE001
                jobs[key] = f"failed: {e}"
        threading.Thread(target=wrap, daemon=True).start()
        return True

    # ---------- pages ----------
    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        cards = []
        for ep in store.list_episodes():
            shots, cues = shots_of(ep)
            manual = sum(1 for _ in (config.episode_dir(ep)).rglob("MANUAL_*.md"))
            blocked = sum(1 for s in shots for v in s["stages"].values() if v["status"] == "blocked")
            cards.append({"name": ep, "shots": len(shots), "cues": len(cues), "stats": stage_stats(shots),
                          "manual": manual, "blocked": blocked, "duration": sum(s["duration_s"] for s in shots)})
        pending = [ep for ep in _episodes_on_disk() if ep not in store.list_episodes()]
        pending_info = {ep: {"script": (config.episode_dir(ep) / "script.md").exists(),
                             "manual": sum(1 for _ in config.episode_dir(ep).rglob("MANUAL_*.md"))} for ep in pending}
        return render(request, "dashboard.html", cards=cards, pending=pending, pending_info=pending_info, jobs=jobs)

    @app.get("/ep/{ep}", response_class=HTMLResponse)
    def board(request: Request, ep: str, status: str = "", stage: str = ""):
        shots, cues = shots_of(ep)
        if status:
            shots = [s for s in shots if any((st == stage or not stage) and v["status"] == status for st, v in s["stages"].items())]
        manual = sum(1 for _ in config.episode_dir(ep).rglob("MANUAL_*.md"))   # same count as the dashboard and the desk
        return render(request, "episode.html", ep=ep, shots=shots, cues=cues, stats=stage_stats(shots_of(ep)[0]),
                      status=status, stage=stage, jobs=jobs, manual=manual)

    @app.get("/ep/{ep}/shot/{sid}", response_class=HTMLResponse)
    def shot(request: Request, ep: str, sid: str):
        row = store.get_shot(ep, sid)
        sd = config.shot_dir(ep, sid) if not sid.startswith("music:") else config.episode_dir(ep) / "audio" / "music" / sid[6:]
        files = {}
        for st, pattern in VIEWABLE.items():
            d = sd / STAGE_DIRS.get(st, "")
            cands = sorted(d.glob(pattern)) if d.exists() else []
            approved = next(iter(d.glob("approved.*")), None) if d.exists() else None
            files[st] = {"candidates": [_rel(config, ep, p) for p in cands], "approved": _rel(config, ep, approved) if approved else None,
                         "requests": [p.name for p in d.glob("MANUAL_*.md")] if d.exists() else []}
        if sid.startswith("music:"):
            files["music"] = {"candidates": [_rel(config, ep, p) for p in sd.glob("cue.*")], "approved": None,
                              "requests": [p.name for p in sd.glob("MANUAL_*.md")]}
        prompts = json.loads((sd / "prompts.json").read_text(encoding="utf-8")) if (sd / "prompts.json").exists() else []
        return render(request, "shot.html", ep=ep, s=row, files=files, prompts=prompts,
                      approvals=[a for a in store.list_approvals(ep) if a["shot_id"] == sid])

    @app.get("/ep/{ep}/manual", response_class=HTMLResponse)
    def manual(request: Request, ep: str):
        items = []
        for req in sorted(config.episode_dir(ep).rglob("MANUAL_*.md")):
            text = req.read_text(encoding="utf-8")
            m = re.search(r"Save your result as: `(.+?)`", text)
            prompt = text.split("## Prompt", 1)[1].split("## Reference files", 1)[0].strip() if "## Prompt" in text else ""
            refs = text.split("## Reference files", 1)[1].split("## Parameters", 1)[0].strip() if "## Reference files" in text else ""
            items.append({"title": text.splitlines()[0].lstrip("# "), "target": m.group(1) if m else "", "prompt": prompt,
                          "refs": refs, "file": str(req), "short": Path(m.group(1)).name if m else ""})
        return render(request, "manual.html", ep=ep, items=items, jobs=jobs)

    @app.get("/usage", response_class=HTMLResponse)
    def usage(request: Request):
        today = date.today().isoformat()
        quotas = []
        for name, p in config.providers.items():
            if p.limits.get("per_day"):
                used = store.usage_today(name)[0]
                quotas.append({"provider": name, "used": used, "limit": p.limits["per_day"],
                               "pct": min(100, int(100 * used / p.limits["per_day"]))})
        return render(request, "usage.html", rows=store.usage_summary(), today=store.usage_summary(today), quotas=quotas)

    @app.get("/providers", response_class=HTMLResponse)
    def providers(request: Request):
        chains = {st: [n for n in s.chain] for st, s in config.pipeline.stages.items()}
        return render(request, "providers.html", providers=config.providers, chains=chains,
                      files=[str(p.relative_to(config.root)) for p in sorted((config.root / "config").glob("*.*"))])

    @app.get("/episodes/new", response_class=HTMLResponse)
    def new_episode(request: Request):
        return render(request, "new_episode.html")

    @app.post("/episodes/new")
    async def create_episode(name: str = Form(...), idea: str = Form(""), script: str = Form(""), script_file: UploadFile | None = None):
        from shotwise.stages.runner import resume
        from shotwise.providers.base import ManualRequired
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "episode"
        ep = config.episode_dir(slug)
        ep.mkdir(parents=True, exist_ok=True)
        if script_file and script_file.filename:
            (ep / "script.md").write_bytes(await script_file.read())
        elif script.strip():
            (ep / "script.md").write_text(script, encoding="utf-8")
        (ep / "idea.md").write_text(idea.strip() or name, encoding="utf-8")

        def go():
            try:
                resume(config, store, slug)
            except ManualRequired:
                pass                                              # shows up on the Manual desk
        background(f"{slug}:resume", go)
        return RedirectResponse(f"/?msg=generating+{slug}", status_code=303)

    @app.get("/settings", response_class=HTMLResponse)
    def settings(request: Request):
        from shotwise.config import STAGE_CAPABILITY
        rows = []
        for st, s in config.pipeline.stages.items():
            if st not in STAGE_CAPABILITY:
                continue
            caps = STAGE_CAPABILITY[st]
            active = next((n for n in s.chain if config.providers[n].enabled and not config.providers[n].is_manual), None)
            rows.append({"stage": st, "active": active or "manual (you)", "chain": s.chain,
                         "options": [n for n, p in config.providers.items() if p.capability in caps]})
        provs = [{"name": n, "type": p.type, "model": p.model or p.workflow or "", "enabled": p.enabled, "manual": p.is_manual,
                  "key_env": p.api_key_env or "", "key_set": bool(p.api_key()) if p.api_key_env else None}
                 for n, p in config.providers.items()]
        return render(request, "settings.html", rows=rows, provs=provs, types=sorted(_TYPE_LABELS.items()),
                      cfg_files=[p.name for p in sorted((config.root / "config").glob("*.*"))])

    @app.post("/settings/use")
    def settings_use(stage: str = Form(...), provider: str = Form(...)):
        pipe = _read_cfg("pipeline")
        chain = pipe["stages"][stage]["chain"]
        pipe["stages"][stage]["chain"] = [provider] + [n for n in chain if n != provider]
        _write_cfg("pipeline", pipe)
        provs = _read_cfg("providers")
        provs["providers"][provider]["enabled"] = True
        _write_cfg("providers", provs)
        _reload()
        return RedirectResponse(f"/settings?msg={stage}+now+uses+{provider}", status_code=303)

    @app.post("/settings/provider/add")
    def settings_add(name: str = Form(...), type: str = Form(...), model: str = Form(""), api_key: str = Form(""),
                     base_url: str = Form(""), workflow: str = Form("")):
        from shotwise.config import STAGE_CAPABILITY
        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
        block = {"type": type, "enabled": True}
        if model:
            block["model"] = model
        if base_url:
            block["base_url"] = base_url
        if workflow:
            block["workflow"] = workflow
        if api_key:
            block["api_key_env"] = f"{slug.upper()}_API_KEY"
            _set_env(block["api_key_env"], api_key.strip())
        provs = _read_cfg("providers")
        provs["providers"][slug] = block
        _write_cfg("providers", provs)
        pipe = _read_cfg("pipeline")
        cap = type.split(".", 1)[0]
        for st, caps in STAGE_CAPABILITY.items():
            if cap in caps and st in pipe["stages"]:
                chain = pipe["stages"][st]["chain"]
                if slug not in chain:
                    first_manual = next((i for i, n in enumerate(chain) if n.startswith("manual")), len(chain))
                    chain.insert(first_manual, slug)              # available as a fallback; "Use" makes it active
        _write_cfg("pipeline", pipe)
        _reload()
        return RedirectResponse(f"/settings?msg=added+{slug}", status_code=303)

    @app.post("/settings/provider/{name}/toggle")
    def settings_toggle(name: str):
        provs = _read_cfg("providers")
        provs["providers"][name]["enabled"] = not provs["providers"][name].get("enabled", True)
        _write_cfg("providers", provs)
        _reload()
        return RedirectResponse("/settings", status_code=303)

    @app.post("/settings/provider/{name}/delete")
    def settings_delete(name: str):
        provs = _read_cfg("providers")
        provs["providers"].pop(name, None)
        _write_cfg("providers", provs)
        pipe = _read_cfg("pipeline")
        for s in pipe["stages"].values():
            s["chain"] = [n for n in s.get("chain", []) if n != name]
        _write_cfg("pipeline", pipe)
        _reload()
        return RedirectResponse(f"/settings?msg=removed+{name}", status_code=303)

    # ---------- actions ----------
    @app.post("/ep/{ep}/shot/{sid}/{stage}/approve")
    def approve(request: Request, ep: str, sid: str, stage: str, candidate: str = Form(...), note: str = Form("")):
        d = config.shot_dir(ep, sid) / STAGE_DIRS.get(stage, stage)
        src = d / Path(candidate).name
        for old in d.glob("approved.*"):
            old.unlink()
        shutil.copyfile(src, d / f"approved{src.suffix}")
        store.set_status(ep, sid, stage, "approved", src.name)
        store.record_approval(ep, sid, stage, "approve", note or src.name)
        return RedirectResponse(f"/ep/{ep}/shot/{sid}?msg=approved+{src.name}", status_code=303)

    @app.post("/ep/{ep}/shot/{sid}/{stage}/reject")
    def reject(ep: str, sid: str, stage: str, note: str = Form("")):
        store.set_field(ep, sid, "note", note)
        store.set_status(ep, sid, stage, "pending", f"regenerate: {note}"[:120])
        store.record_approval(ep, sid, stage, "reject", note)
        d = config.shot_dir(ep, sid) / STAGE_DIRS.get(stage, stage)
        for old in d.glob("approved.*"):
            old.unlink()
        return RedirectResponse(f"/ep/{ep}/shot/{sid}?msg=marked+for+regeneration", status_code=303)

    @app.post("/ep/{ep}/shot/{sid}/lane")
    def lane(ep: str, sid: str, lane: str = Form(...)):
        store.set_field(ep, sid, "lane", lane)
        bpath = config.episode_dir(ep) / "breakdown.json"
        if bpath.exists():
            b = json.loads(bpath.read_text(encoding="utf-8"))
            for sc in b["scenes"]:
                for sh in sc["shots"]:
                    if sh["id"] == sid:
                        sh["lane"] = lane
            bpath.write_text(json.dumps(b, indent=2), encoding="utf-8")
        return RedirectResponse(f"/ep/{ep}/shot/{sid}?msg=lane+set+to+{lane}", status_code=303)

    @app.post("/ep/{ep}/run/{stage}")
    def run_stage_bg(ep: str, stage: str, shots: str = Form("")):
        from shotwise.stages.runner import run_stage
        ids = [s for s in shots.split(",") if s] or None
        started = background(f"{ep}:{stage}", lambda: run_stage(config, store, stage, ep, ids))
        return RedirectResponse(f"/ep/{ep}?msg=" + ("started+" + stage if started else stage + "+already+running"), status_code=303)

    @app.post("/ep/{ep}/resume")
    def resume_bg(ep: str):
        from shotwise.stages.runner import resume
        started = background(f"{ep}:resume", lambda: resume(config, store, ep))
        return RedirectResponse(f"/ep/{ep}?msg=" + ("resume+started" if started else "resume+already+running"), status_code=303)

    @app.post("/ep/{ep}/breakdown")
    def breakdown_bg(ep: str):
        from shotwise.stages import breakdown
        from shotwise.providers.base import ManualRequired

        def go():
            try:
                if not (config.episode_dir(ep) / "script.md").exists():
                    from shotwise.stages import script
                    script.run(config, store, ep)                 # writes the script first when only an idea exists
                breakdown.run(config, store, ep)
            except ManualRequired:
                pass                                              # the request file now exists; shown on the Manual page
        started = background(f"{ep}:breakdown", go)
        return RedirectResponse(f"/ep/{ep}/manual?msg=" + ("breakdown+started" if started else "already+running"), status_code=303)

    @app.post("/ep/{ep}/manual/upload")
    async def upload(ep: str, target: str = Form(...), file: UploadFile | None = None, text: str = Form("")):
        dest = Path(target).resolve()
        if config.episode_dir(ep).resolve() not in dest.parents:
            return HTMLResponse("target must be inside the episode folder", status_code=400)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if file and file.filename:
            dest.write_bytes(await file.read())
        elif text.strip():
            dest.write_text(text, encoding="utf-8")
        else:
            return RedirectResponse(f"/ep/{ep}/manual?msg=nothing+uploaded", status_code=303)
        (dest.parent / request_name(dest.name)).unlink(missing_ok=True)
        return RedirectResponse(f"/ep/{ep}/manual?msg=saved+{dest.name}", status_code=303)

    return app


def _rel(config, ep, p: Path) -> str:
    return "/media/" + p.relative_to(config.root / "episodes").as_posix()
