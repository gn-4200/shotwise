import json
from pathlib import Path

from shotwise.providers.base import Job, ManualRequired, Result


def request_name(expected: str) -> str:
    return f"MANUAL_{expected}.md"


class _Manual:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg

    def healthcheck(self) -> bool:
        return True

    def expected(self, job: Job) -> str:
        raise NotImplementedError

    def run(self, job: Job) -> Result:
        out = job.workdir / self.expected(job)
        req = job.workdir / request_name(out.name)
        if out.exists() and out.stat().st_size > 0:
            req.unlink(missing_ok=True)                        # the human delivered; clear the request
            return self.wrap(out, job)
        job.workdir.mkdir(parents=True, exist_ok=True)
        req.write_text(self.instructions(job, out), encoding="utf-8")
        raise ManualRequired(req, out)

    def instructions(self, job: Job, out: Path) -> str:
        refs = "\n".join(f"- {k}: `{v}`" for k, v in job.inputs.items()) or "- none"
        params = "\n".join(f"- {k}: {v}" for k, v in job.params.items() if k != "attempt") or "- none"
        return (f"# Manual step: {job.stage} for {job.shot_id or job.episode}\n\n"
                f"Save your result as: `{out}`\n\n## Prompt\n\n{job.prompt}\n\n"
                f"## Reference files\n{refs}\n\n## Parameters\n{params}\n\n"
                f"Then run: `shotwise resume {job.episode}`\n")


class ManualText(_Manual):
    def expected(self, job):
        return "response.json" if job.schema else "response.md"

    def wrap(self, out, job):
        text = out.read_text(encoding="utf-8")
        return Result(files=[out], data=json.loads(text) if job.schema else {"text": text})


class ManualFile(_Manual):
    """Images, video, audio: the stage sets params['expected_filename'], the human saves that file."""

    def expected(self, job):
        return job.params["expected_filename"].format(attempt=1)

    def wrap(self, out, job):
        return Result(files=[out])
