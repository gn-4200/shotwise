from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

ErrorKind = Literal["auth", "quota", "timeout", "invalid_output", "transient", "unavailable", "refusal", "qc_failed"]
RETRY_SAME_PROVIDER = {"timeout", "transient", "invalid_output", "qc_failed"}


class ProviderError(Exception):
    def __init__(self, kind: ErrorKind, message: str, retryable: bool | None = None):
        super().__init__(f"[{kind}] {message}")
        self.kind = kind
        self.retryable = retryable if retryable is not None else kind in RETRY_SAME_PROVIDER


class ManualRequired(Exception):
    """A human must supply the output. The request file explains what and where."""

    def __init__(self, request_file: Path, expected_output: Path):
        super().__init__(f"manual input required, see {request_file}")
        self.request_file, self.expected_output = request_file, expected_output


class Deferred(Exception):
    """The job was queued for a remote worker. Check again on `shotwise resume`."""

    def __init__(self, job_id: str):
        super().__init__(f"queued as {job_id}")
        self.job_id = job_id


@dataclass
class Job:
    stage: str
    episode: str
    shot_id: str | None
    workdir: Path                                            # where outputs are written
    prompt: str = ""
    inputs: dict[str, Path] = field(default_factory=dict)    # keyframe, ref_image, audio, voice_ref ...
    params: dict[str, Any] = field(default_factory=dict)     # duration_s, width, seed, expected_filename ...
    schema: dict | None = None                               # JSON schema for structured LLM output

    def expected_filename(self) -> str:
        name = self.params.get("expected_filename", "output")
        return name.format(attempt=self.params.get("attempt", 1))


@dataclass
class Result:
    files: list[Path] = field(default_factory=list)
    data: dict | None = None
    provider: str = ""
    units: float = 0.0                                       # tokens, seconds generated, characters spoken
    cost_usd: float = 0.0


@runtime_checkable
class Provider(Protocol):
    name: str

    def run(self, job: Job) -> Result: ...
    def healthcheck(self) -> bool: ...
