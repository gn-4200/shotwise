"""Queue transport: wraps a ComfyUI provider so the job runs on a remote worker (Kaggle, Colab, another PC)."""
import json
import shutil
import uuid
from pathlib import Path

from shotwise.providers.base import Deferred, Job, ProviderError, Result


class RemoteQueue:
    def __init__(self, inner, queue_dir: Path):
        self.inner, self.queue, self.name = inner, queue_dir, inner.name

    def healthcheck(self):
        return True

    def run(self, job: Job) -> Result:
        marker = job.workdir / ".queued"
        if marker.exists():
            job_id = marker.read_text().strip()
            done = self.queue / "done" / job_id
            result = done / "result.json"
            if not result.exists():
                raise Deferred(job_id)                            # still running, or not synced yet
            info = json.loads(result.read_text())
            marker.unlink()
            if not info["ok"]:
                raise ProviderError("transient", f"worker: {info['error']}")
            files = []
            for i, name in enumerate(info["files"]):
                dest = job.workdir / (job.expected_filename() if i == 0 and "expected_filename" in job.params else name)
                shutil.move(done / name, dest)
                files.append(dest)
            return Result(files=files, units=self.inner.units(job))
        job_id = uuid.uuid4().hex[:12]
        inputs_dir = self.queue / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        m = self.inner.cfg.inputs
        spec = {"id": job_id, "workflow": self.inner.workflow_path.name, "set": {}, "files": {}}
        if "prompt" in m:
            spec["set"][m["prompt"]] = job.prompt
        for logical, src in job.inputs.items():
            if logical in m:
                dest = inputs_dir / f"{job_id}_{src.name}"
                shutil.copy(src, dest)
                spec["files"][m[logical]] = dest.name
        for key in ("seed", "width", "height", "length", "seconds", "negative", "lyrics"):
            if key in m and key in job.params:
                spec["set"][m[key]] = job.params[key]
        (self.queue / "pending").mkdir(parents=True, exist_ok=True)
        (self.queue / "pending" / f"{job_id}.json").write_text(json.dumps(spec, indent=2))
        job.workdir.mkdir(parents=True, exist_ok=True)
        marker.write_text(job_id)
        raise Deferred(job_id)
