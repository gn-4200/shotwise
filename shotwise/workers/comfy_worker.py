"""Queue worker: runs on the GPU machine or inside a Kaggle/Colab notebook. Claims queue/pending/*.json,
runs the workflow in the local ComfyUI, writes queue/done/<id>/ with result.json."""
import argparse
import json
import time
from pathlib import Path

from shotwise.providers.comfy import ComfyClient, set_input


def serve(queue: Path, comfy_url: str, workflows: Path, once: bool, poll_s: int = 15):
    client = ComfyClient(comfy_url)
    for d in ("pending", "running", "done", "inputs"):
        (queue / d).mkdir(parents=True, exist_ok=True)
    while True:
        jobs = sorted((queue / "pending").glob("*.json"))
        for job_file in jobs:
            running = queue / "running" / job_file.name
            try:
                job_file.rename(running)                      # atomic claim; a second worker loses the race
            except FileNotFoundError:
                continue
            spec = json.loads(running.read_text())
            out = queue / "done" / spec["id"]
            out.mkdir(parents=True, exist_ok=True)
            try:
                wf = json.loads((workflows / spec["workflow"]).read_text())
                for path, value in spec["set"].items():
                    set_input(wf, path, value)
                for path, fname in spec["files"].items():
                    set_input(wf, path, client.upload(queue / "inputs" / fname))
                files = client.run(wf, out)
                (out / "result.json").write_text(json.dumps({"ok": True, "files": [f.name for f in files]}))
                print(f"done {spec['id']}: {[f.name for f in files]}")
            except Exception as e:                            # noqa: BLE001 - the worker must keep draining
                (out / "result.json").write_text(json.dumps({"ok": False, "error": str(e)}))
                print(f"failed {spec['id']}: {e}")
            finally:
                running.unlink(missing_ok=True)
        if once and not jobs:
            return
        time.sleep(poll_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True)
    ap.add_argument("--comfy", default="http://127.0.0.1:8188")
    ap.add_argument("--workflows", default="workflows")
    ap.add_argument("--once", action="store_true", help="drain the queue and exit (Kaggle sessions)")
    a = ap.parse_args()
    serve(Path(a.queue), a.comfy, Path(a.workflows), a.once)


if __name__ == "__main__":
    main()
