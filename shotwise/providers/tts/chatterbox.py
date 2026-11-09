from shotwise.providers.base import Job, ProviderError, Result


class ChatterboxTTS:
    """pip install chatterbox-tts torchaudio. Clones a voice from bible/characters/<name>/voice.wav."""

    def __init__(self, name, cfg):
        self.name, self.cfg, self._model = name, cfg, None

    def _m(self):
        if self._model is None:
            try:
                from chatterbox.tts import ChatterboxTTS as CB
            except ImportError:
                raise ProviderError("unavailable", "chatterbox-tts is not installed (pip install -e '.[tts]')", retryable=False)
            self._model = CB.from_pretrained(device=self.cfg.params.get("device", "cuda"))
        return self._model

    def healthcheck(self) -> bool:
        try:
            import chatterbox  # noqa: F401
            return True
        except ImportError:
            return False

    def run(self, job: Job) -> Result:
        model = self._m()
        try:
            import torchaudio as ta
        except ImportError:
            raise ProviderError("unavailable", "torchaudio is not installed (pip install -e '.[tts]')", retryable=False)
        ref = job.inputs.get("voice_ref")
        wav = model.generate(job.prompt, audio_prompt_path=str(ref) if ref and ref.exists() else None,
                                 exaggeration=job.params.get("exaggeration", self.cfg.params.get("exaggeration", 0.5)),
                                 cfg_weight=self.cfg.params.get("cfg_weight", 0.5))
        job.workdir.mkdir(parents=True, exist_ok=True)
        out = job.workdir / job.expected_filename()
        ta.save(str(out), wav, model.sr)
        return Result(files=[out], units=float(len(job.prompt)))
