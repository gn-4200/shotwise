"""Populate the pilot episode with placeholder keyframes and realistic statuses so the review page can be
previewed without a GPU. Usage: python scripts/demo_assets.py [episode]   (needs pillow)"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shotwise.config import load_config          # noqa: E402
from shotwise.store import make_store            # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EP = sys.argv[1] if len(sys.argv) > 1 else "ep00-pilot"
PALETTES = {"s01": ((232, 148, 58), (38, 52, 92)), "s02": ((46, 125, 95), (14, 22, 40)), "s03": ((70, 90, 140), (10, 12, 24))}


def frame(path: Path, sid: str, n: int, text: str):
    a, b = PALETTES.get(sid[:3], ((120, 120, 160), (20, 20, 40)))
    img = Image.new("RGB", (1280, 720))
    px = img.load()
    for y in range(720):
        t = y / 719
        for x in range(0, 1280):
            px[x, y] = tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))
    d = ImageDraw.Draw(img)
    d.ellipse((880 - 60 * n, 140, 1180 - 60 * n, 440), fill=(255, 220, 150) if n == 1 else (200, 230, 255))
    d.rectangle((0, 560, 1280, 720), fill=(10, 10, 16))
    big = ImageFont.load_default(size=56)
    small = ImageFont.load_default(size=28)
    d.text((48, 580), f"{sid}  candidate {n}", font=big, fill=(245, 245, 245))
    d.text((48, 650), text[:90], font=small, fill=(180, 180, 190))
    img.save(path)


def main():
    cfg = load_config(ROOT)
    store = make_store(cfg)
    shots = [s for s in store.list_shots(EP) if not s["id"].startswith("music:")]
    approve = {"s01_01", "s01_02", "s01_03", "s02_01", "s03_01", "s03_03"}
    for s in shots:
        kf = cfg.shot_dir(EP, s["id"]) / "keyframes"
        kf.mkdir(parents=True, exist_ok=True)
        for req in kf.glob("MANUAL_*.md"):
            req.unlink()
        for n in (1, 2):
            frame(kf / f"cand_{n}.png", s["id"], n, s["action"])
        if s["id"] in approve:
            (kf / "approved.png").write_bytes((kf / "cand_1.png").read_bytes())
            store.set_status(EP, s["id"], "keyframes", "approved", "cand_1.png")
            store.record_approval(EP, s["id"], "keyframes", "approve", "cand_1.png")
        else:
            store.set_status(EP, s["id"], "keyframes", "needs_review", "comfy_qwen_image")
    store.set_status(EP, "s01_02", "video", "queued", "kaggle worker 7c1e2a")
    store.set_status(EP, "s01_03", "video", "blocked", "comfy_wan22: ComfyUI not reachable; manual_video: waiting")
    store.set_status(EP, "s03_03", "video", "queued", "kaggle worker 7c1e2a")
    store.set_status(EP, "s02_01", "video", "needs_review", "comfy_wan22")
    store.set_status(EP, "s01_03", "voice", "done", "chatterbox_local")
    store.set_status(EP, "s01_04", "voice", "done", "chatterbox_local")
    store.record_approval(EP, "s01_04", "keyframes", "reject", "Tariq's beard is too short, lantern should be green")
    store.set_field(EP, "s01_04", "note", "Tariq's beard is too short, lantern should be green")
    store.set_field(EP, "s03_03", "lane", "premium")
    for name, units in (("gemini_free", 8200), ("comfy_qwen_image", 22), ("chatterbox_local", 640)):
        store.record_usage(name, units, 0.0, True)
    print(f"demo assets written for {EP}: {len(shots)} shots")


if __name__ == "__main__":
    main()
