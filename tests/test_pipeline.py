import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = json.loads((ROOT / "tests" / "sample_breakdown.json").read_text(encoding="utf-8"))


@pytest.fixture
def project(tmp_path, monkeypatch):
    for d in ("config", "prompts", "bible"):
        shutil.copytree(ROOT / d, tmp_path / d)
    shutil.copytree(ROOT / "episodes" / "ep00-pilot", tmp_path / "episodes" / "ep00-pilot",
                    ignore=shutil.ignore_patterns("shots", "breakdown", "breakdown.json", "out", "audio"))
    # the tests bring their own cast: the story bible changes from series to series
    shutil.copy(ROOT / "tests" / "fixtures" / "cast.yaml", tmp_path / "bible" / "cast.yaml")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _load(project):
    from shotwise.config import load_config
    from shotwise.store import make_store
    cfg = load_config(project)
    return cfg, make_store(cfg)


def test_config_loads_and_validates(project):
    cfg, _ = _load(project)
    assert cfg.pipeline.stages["breakdown"].chain[-1] == "manual_text"
    assert cfg.providers["comfy_wan22"].base_url.startswith("http://127.0.0.1")


def test_bad_chain_is_rejected(project):
    from shotwise.config import load_config
    p = project / "config" / "pipeline.json"
    pipe = json.loads(p.read_text(encoding="utf-8"))
    pipe["stages"]["breakdown"]["chain"] = ["manual_video"]
    p.write_text(json.dumps(pipe), encoding="utf-8")
    with pytest.raises(ValueError, match="needs a llm provider"):
        load_config(project)


def test_breakdown_falls_back_to_manual_then_resumes(project):
    from shotwise.providers.base import ManualRequired
    from shotwise.stages import breakdown
    cfg, store = _load(project)
    with pytest.raises(ManualRequired) as e:
        breakdown.run(cfg, store, "ep00-pilot")
    req = e.value.request_file
    assert req.exists() and "SERIES BIBLE" in req.read_text(encoding="utf-8")
    assert any(r["provider"] == "gemini_free" and not r["ok"] for r in store.data["usage"])   # auth failure recorded
    e.value.expected_output.write_text(json.dumps(SAMPLE), encoding="utf-8")
    b = breakdown.run(cfg, store, "ep00-pilot")
    assert len(store.list_shots("ep00-pilot")) == sum(len(s.shots) for s in b.scenes) == 11
    assert not req.exists()
    assert (cfg.shot_dir("ep00-pilot", "s01_03") / "shot.json").exists()


def test_keyframes_stage_writes_manual_requests_and_video_waits(project):
    from shotwise.stages import breakdown
    from shotwise.stages.runner import run_stage
    cfg, store = _load(project)
    (project / "episodes" / "ep00-pilot" / "breakdown").mkdir()
    (project / "episodes" / "ep00-pilot" / "breakdown" / "response.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    breakdown.run(cfg, store, "ep00-pilot")
    report = run_stage(cfg, store, "keyframes", "ep00-pilot")
    assert len(report["manual"]) == 11 and not report["blocked"]
    kf = cfg.shot_dir("ep00-pilot", "s01_03") / "keyframes"
    assert (kf / "MANUAL_cand_1.png.md").exists() and (kf / "MANUAL_cand_2.png.md").exists()
    assert "Ayla, 24, short black hair" in (kf / "MANUAL_cand_1.png.md").read_text(encoding="utf-8")
    report = run_stage(cfg, store, "video", "ep00-pilot")
    assert "s01_01" in report["skipped"] and "s01_03" in report["waiting"]
    (kf / "cand_1.png").write_bytes(b"png")                       # a human delivers one candidate
    report = run_stage(cfg, store, "keyframes", "ep00-pilot", shot_ids=["s01_03"])
    assert report["manual"] == ["s01_03"] and not (kf / "MANUAL_cand_1.png.md").exists()


def test_cli_config_check_runs(project):
    from shotwise.cli import app
    result = CliRunner().invoke(app, ["--root", str(project), "config-check"])
    assert result.exit_code == 0, result.output
    assert "gemini_free" in result.output and "stage breakdown" in result.output


def test_review_pages_render(project):
    from fastapi.testclient import TestClient
    from shotwise.review.app import create_app
    from shotwise.stages import breakdown
    cfg, store = _load(project)
    (project / "episodes" / "ep00-pilot" / "breakdown").mkdir()
    (project / "episodes" / "ep00-pilot" / "breakdown" / "response.json").write_text(json.dumps(SAMPLE), encoding="utf-8")
    breakdown.run(cfg, store, "ep00-pilot")
    client = TestClient(create_app(cfg, store))
    for url in ("/", "/ep/ep00-pilot", "/ep/ep00-pilot/shot/s01_03", "/ep/ep00-pilot/manual", "/usage", "/providers",
                "/settings", "/episodes/new"):
        r = client.get(url)
        assert r.status_code == 200, url
    r = client.post("/settings/use", data={"stage": "breakdown", "provider": "claude"}, follow_redirects=False)
    assert r.status_code == 303
    pipe = json.loads((project / "config" / "pipeline.json").read_text(encoding="utf-8"))
    assert pipe["stages"]["breakdown"]["chain"][0] == "claude"
    r = client.post("/settings/provider/add", data={"name": "my-llm", "type": "llm.openai", "model": "gpt-5", "api_key": "sk-test"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "MY_LLM_API_KEY=sk-test" in (project / ".env").read_text(encoding="utf-8")
    assert "my_llm" in json.loads((project / "config" / "providers.json").read_text(encoding="utf-8"))["providers"]
    r = client.post("/episodes/new", data={"name": "Ep 01 Test", "idea": "Ayla finds the signal."}, follow_redirects=False)
    assert r.status_code == 303 and (project / "episodes" / "ep-01-test" / "idea.md").exists()
    r = client.post("/ep/ep00-pilot/shot/s01_03/lane", data={"lane": "premium"}, follow_redirects=False)
    assert r.status_code == 303 and store.get_shot("ep00-pilot", "s01_03")["lane"] == "premium"
