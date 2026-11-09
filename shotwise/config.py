from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)(?::-([^}]*))?\}")  # ${VAR} and ${VAR:-default}

STAGE_CAPABILITY = {
    "script": {"llm"}, "breakdown": {"llm"}, "prompts": {"llm"}, "keyframes": {"image"}, "video": {"video"},
    "voice": {"tts"}, "lipsync": {"lipsync", "video"}, "music": {"music"}, "publish": {"publish"},
}


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_RE.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


class ProviderConfig(BaseModel):
    type: str                                              # "llm.gemini", "video.comfyui", "tts.manual" ...
    enabled: bool = True
    model: str | None = None
    api_key_env: str | None = None                         # name of the env var, never the key itself
    base_url: str | None = None
    workflow: str | None = None                            # ComfyUI workflow JSON (API format)
    inputs: dict[str, str] = Field(default_factory=dict)   # logical input -> "node.inputs.field"
    limits: dict[str, int] = Field(default_factory=dict)   # {"per_day": 150}
    cost: dict[str, float] = Field(default_factory=dict)   # {"per_second_usd": 0.10}
    params: dict[str, Any] = Field(default_factory=dict)   # free-form, passed to the adapter

    @property
    def capability(self) -> str:
        return self.type.split(".", 1)[0]

    @property
    def is_manual(self) -> bool:
        return self.type.endswith(".manual")

    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) or None if self.api_key_env else None


class StageConfig(BaseModel):
    chain: list[str] = Field(default_factory=list)
    attempts: int = 1
    candidates: int = 1
    gate: bool = False
    qc: dict[str, Any] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)


class StorageConfig(BaseModel):
    backend: Literal["sqlite", "json"] = "sqlite"
    path: str = "state/shotwise.db"


class WorkersConfig(BaseModel):
    transport: Literal["local", "rclone"] = "local"
    queue_dir: str = "queue"
    remote: str | None = None


class PipelineConfig(BaseModel):
    storage: StorageConfig = StorageConfig()
    workers: WorkersConfig = WorkersConfig()
    stages: dict[str, StageConfig]


class ShotwiseConfig(BaseModel):
    providers: dict[str, ProviderConfig]
    pipeline: PipelineConfig
    root: Path

    @model_validator(mode="after")
    def _chains_reference_known_providers(self) -> "ShotwiseConfig":
        for stage, cfg in self.pipeline.stages.items():
            want = STAGE_CAPABILITY.get(stage)
            for name in cfg.chain:
                if name not in self.providers:
                    raise ValueError(f"stage '{stage}' references unknown provider '{name}'")
                if want and self.providers[name].capability not in want:
                    raise ValueError(f"stage '{stage}' needs a {'/'.join(sorted(want))} provider; '{name}' is {self.providers[name].type}")
        return self

    # ---- paths ----
    def episode_dir(self, episode: str) -> Path:
        return self.root / "episodes" / episode

    def shot_dir(self, episode: str, shot_id: str) -> Path:
        return self.episode_dir(episode) / "shots" / shot_id

    def bible(self) -> dict:
        cast = yaml.safe_load((self.root / "bible" / "cast.yaml").read_text(encoding="utf-8")) or {}
        style = yaml.safe_load((self.root / "bible" / "style.yaml").read_text(encoding="utf-8")) or {}
        return {"text": (self.root / "bible" / "bible.md").read_text(encoding="utf-8"),
                "characters": cast.get("characters", {}), "locations": cast.get("locations", {}),
                "emotion": cast.get("emotion_exaggeration", {}), "style": style}


def _pick(cfg_dir: Path, stem: str) -> Path:
    for ext in (".yaml", ".yml", ".json"):
        if (p := cfg_dir / f"{stem}{ext}").exists():
            return p
    raise FileNotFoundError(f"config/{stem}.yaml or config/{stem}.json not found in {cfg_dir.parent}")


def _load(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    return _expand_env(data or {})


def load_config(root: Path | str = ".") -> ShotwiseConfig:
    root = Path(root).resolve()
    providers = _load(_pick(root / "config", "providers"))["providers"]
    pipeline = _load(_pick(root / "config", "pipeline"))
    return ShotwiseConfig(providers=providers, pipeline=pipeline, root=root)
