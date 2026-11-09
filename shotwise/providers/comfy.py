"""ComfyUI client and providers. A provider is a workflow file (API format) plus an input mapping in config."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from shotwise.providers.base import Job, ProviderError, Result


def set_input(workflow: dict, path: str, value) -> None:
    """'12.inputs.image' -> workflow['12']['inputs']['image'] = value"""
    node, _, field = path.partition(".inputs.")
    workflow[node]["inputs"][field] = value


class ComfyClient:
    def __init__(self, base_url: str, timeout_s: int = 1800):
        self.base = base_url.rstrip("/")
        self.ws_url = self.base.replace("http", "ws", 1) + "/ws"
        self.timeout_s = timeout_s

    def upload(self, path: Path) -> str:
        boundary = uuid.uuid4().hex
        head = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
                f"Content-Type: application/octet-stream\r\n\r\n").encode()
        body = head + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
        req = urllib.request.Request(f"{self.base}/upload/image", data=body,
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            return json.load(r)["name"]

    def run(self, workflow: dict, out_dir: Path) -> list[Path]:
        import websocket
        client_id = uuid.uuid4().hex
        ws = websocket.create_connection(f"{self.ws_url}?clientId={client_id}", timeout=self.timeout_s)
        payload = json.dumps({"prompt": workflow, "client_id": client_id}).encode()
        req = urllib.request.Request(f"{self.base}/prompt", data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                prompt_id = json.load(r)["prompt_id"]
        except urllib.error.HTTPError as e:
            raise ProviderError("invalid_output", f"ComfyUI rejected the workflow: {e.read()[:400]!r}", retryable=False)
        deadline = time.time() + self.timeout_s
        try:
            while time.time() < deadline:
                msg = ws.recv()
                if isinstance(msg, bytes):
                    continue                                   # preview frames
                evt = json.loads(msg)
                data = evt.get("data", {})
                if data.get("prompt_id") != prompt_id:
                    continue
                if evt["type"] == "executing" and data.get("node") is None:
                    break                                      # finished
                if evt["type"] == "execution_error":
                    raise ProviderError("transient", f"ComfyUI: {data.get('exception_message')}")
            else:
                raise ProviderError("timeout", "ComfyUI generation timed out")
        finally:
            ws.close()
        with urllib.request.urlopen(f"{self.base}/history/{prompt_id}", timeout=60) as r:
            outputs = json.load(r)[prompt_id]["outputs"]
        files: list[Path] = []
        out_dir.mkdir(parents=True, exist_ok=True)
        for node in outputs.values():
            for kind in ("images", "gifs", "videos", "audio"):
                for item in node.get(kind, []):
                    q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                                "type": item.get("type", "output")})
                    dest = out_dir / item["filename"]
                    with urllib.request.urlopen(f"{self.base}/view?{q}", timeout=600) as r:
                        dest.write_bytes(r.read())
                    files.append(dest)
        if not files:
            raise ProviderError("invalid_output", "ComfyUI produced no output files")
        return files


class ComfyBase:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.client = ComfyClient(cfg.base_url or "http://127.0.0.1:8188", cfg.params.get("timeout_s", 1800))
        self.workflow_path = Path(cfg.workflow or "")
        self.detail = ""

    @property
    def template(self) -> dict:
        if not self.workflow_path.exists():
            raise ProviderError("unavailable", f"{self.name}: workflow file {self.workflow_path} not found", retryable=False)
        return json.loads(self.workflow_path.read_text(encoding="utf-8"))

    def healthcheck(self) -> bool:
        if not self.workflow_path.exists():
            self.detail = f"workflow missing: {self.workflow_path}"
            return False
        try:
            urllib.request.urlopen(f"{self.client.base}/system_stats", timeout=3)
            return True
        except Exception:
            self.detail = f"ComfyUI not reachable at {self.client.base}"
            return False

    def build_workflow(self, job: Job) -> dict:
        wf = self.template
        m = self.cfg.inputs
        if "prompt" in m:
            set_input(wf, m["prompt"], job.prompt)
        if "negative" in m:
            set_input(wf, m["negative"], job.params.get("negative", ""))
        if "seed" in m:
            set_input(wf, m["seed"], job.params.get("seed") or int.from_bytes(os.urandom(4), "big"))
        for logical, src in job.inputs.items():                # keyframe, ref_image, video, audio ...
            if logical in m:
                set_input(wf, m[logical], self.client.upload(src))
        for key in ("width", "height", "length", "fps", "steps", "seconds", "lyrics"):
            if key in m and key in job.params:
                set_input(wf, m[key], job.params[key])
        return wf

    def run(self, job: Job) -> Result:
        if not self.healthcheck():
            raise ProviderError("unavailable", f"{self.name}: {self.detail}", retryable=False)
        files = self.client.run(self.build_workflow(job), job.workdir)
        if "expected_filename" in job.params:                   # same names the manual lane uses
            dest = job.workdir / job.expected_filename()
            files[0].replace(dest)
            files[0] = dest
        return Result(files=files, units=self.units(job))

    def units(self, job: Job) -> float:
        return 1.0


class ComfyImage(ComfyBase):
    pass


class ComfyVideo(ComfyBase):
    def units(self, job):
        return float(job.params.get("duration_s", 5))


class ComfyAudio(ComfyBase):
    def units(self, job):
        return float(job.params.get("seconds", 60))
