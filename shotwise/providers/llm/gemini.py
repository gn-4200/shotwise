from shotwise.providers.base import Job, ProviderError, Result
from shotwise.providers.llm._common import parse_json


class GeminiLLM:
    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.model = cfg.model or "gemini-2.5-flash"
        self._client = None

    def _client_(self):
        if self._client is None:
            key = self.cfg.api_key()
            if not key:
                raise ProviderError("auth", f"{self.name}: env var {self.cfg.api_key_env} is not set", retryable=False)
            from google import genai
            self._client = genai.Client(api_key=key)
        return self._client

    def healthcheck(self) -> bool:
        try:
            self._client_().models.get(model=self.model)
            return True
        except Exception:
            return False

    def run(self, job: Job) -> Result:
        from google.genai import errors as genai_errors
        config = {"temperature": self.cfg.params.get("temperature", 0.6)}
        if job.schema:
            config["response_mime_type"] = "application/json"
            config["response_json_schema"] = job.schema
        try:
            resp = self._client_().models.generate_content(model=self.model, contents=job.prompt, config=config)
        except genai_errors.APIError as e:
            kind = "quota" if e.code == 429 else "auth" if e.code in (401, 403) else "transient"
            raise ProviderError(kind, f"gemini {e.code}: {e.message}")
        text = resp.text or ""
        usage = getattr(resp, "usage_metadata", None)
        return Result(data=parse_json(text) if job.schema else {"text": text},
                      units=float(getattr(usage, "total_token_count", 0) or 0))
