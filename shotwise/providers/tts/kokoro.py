from shotwise.providers.base import Job, ProviderError, Result


class KokoroTTS:
    """pip install kokoro soundfile. Fast stock voices, runs on CPU, no cloning."""

    def __init__(self, name, cfg):
        self.name, self.cfg, self._pipe = name, cfg, None

    def _p(self):
        if self._pipe is None:
            try:
                from kokoro import KPipeline
            except ImportError:
                raise ProviderError("unavailable", "kokoro is not installed (pip install -e '.[tts]')", retryable=False)
            self._pipe = KPipeline(lang_code=self.cfg.params.get("lang", "a"))
        return self._pipe

    def healthcheck(self) -> bool:
        try:
            import kokoro  # noqa: F401
            return True
        except ImportError:
            return False

    def run(self, job: Job) -> Result:
        pipe = self._p()
        try:
            import numpy as np
            import soundfile as sf
        except ImportError:
            raise ProviderError("unavailable", "soundfile is not installed (pip install -e '.[tts]')", retryable=False)
        voice = job.params.get("voice") or self.cfg.params.get("voice", "af_heart")
        audio = np.concatenate([a for _, _, a in pipe(job.prompt, voice=voice)])
        job.workdir.mkdir(parents=True, exist_ok=True)
        out = job.workdir / job.expected_filename()
        sf.write(str(out), audio, 24000)
        return Result(files=[out], units=float(len(job.prompt)))
