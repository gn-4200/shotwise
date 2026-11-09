from importlib import import_module

from shotwise.config import ProviderConfig, ShotwiseConfig
from shotwise.providers.base import Provider

_ADAPTERS: dict[str, str] = {
    "llm.gemini":      "shotwise.providers.llm.gemini:GeminiLLM",
    "llm.anthropic":   "shotwise.providers.llm.claude:ClaudeLLM",
    "llm.openai":      "shotwise.providers.llm.openai_compat:OpenAILLM",
    "llm.manual":      "shotwise.providers.manual:ManualText",
    "image.comfyui":   "shotwise.providers.comfy:ComfyImage",
    "image.manual":    "shotwise.providers.manual:ManualFile",
    "video.comfyui":   "shotwise.providers.comfy:ComfyVideo",
    "video.manual":    "shotwise.providers.manual:ManualFile",
    "lipsync.comfyui": "shotwise.providers.comfy:ComfyVideo",
    "music.comfyui":   "shotwise.providers.comfy:ComfyAudio",
    "music.manual":    "shotwise.providers.manual:ManualFile",
    "tts.chatterbox":  "shotwise.providers.tts.chatterbox:ChatterboxTTS",
    "tts.kokoro":      "shotwise.providers.tts.kokoro:KokoroTTS",
    "tts.manual":      "shotwise.providers.manual:ManualFile",
    "publish.youtube": "shotwise.providers.publish.youtube:YouTubePublisher",
}


def register(type_name: str, dotted_path: str) -> None:
    """Plugins call this to add a provider type without editing the table above."""
    _ADAPTERS[type_name] = dotted_path


def build(name: str, cfg: ProviderConfig) -> Provider:
    try:
        module, cls = _ADAPTERS[cfg.type].split(":")
    except KeyError:
        raise ValueError(f"provider '{name}' has unknown type '{cfg.type}'. Known: {sorted(_ADAPTERS)}")
    return getattr(import_module(module), cls)(name, cfg)


def chain_for(config: ShotwiseConfig, stage: str, force: str | None = None) -> list[Provider]:
    if force:
        return [build(force, config.providers[force])]
    names = config.pipeline.stages[stage].chain
    return [build(n, config.providers[n]) for n in names if config.providers[n].enabled]
