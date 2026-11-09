from shotwise.providers.base import Job, ProviderError, Result
from shotwise.providers.llm._common import parse_json


class OpenAILLM:
    """OpenAI, and any OpenAI-compatible server (Ollama, LM Studio) via base_url."""

    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.model = cfg.model or "gpt-5"
        self._client = None

    def _client_(self):
        if self._client is None:
            from openai import OpenAI
            if not self.cfg.api_key() and not self.cfg.base_url:
                raise ProviderError("auth", f"{self.name}: env var {self.cfg.api_key_env} is not set", retryable=False)
            self._client = OpenAI(api_key=self.cfg.api_key() or "local", base_url=self.cfg.base_url)
        return self._client

    def healthcheck(self) -> bool:
        try:
            self._client_().models.list()
            return True
        except Exception:
            return False

    def run(self, job: Job) -> Result:
        from openai import APIConnectionError, APIStatusError, AuthenticationError, RateLimitError
        kwargs = {"model": self.model, "messages": [{"role": "user", "content": job.prompt}]}
        if job.schema:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": {"name": "output", "schema": job.schema}}
        try:
            resp = self._client_().chat.completions.create(**kwargs)
        except RateLimitError as e:
            raise ProviderError("quota", str(e))
        except AuthenticationError as e:
            raise ProviderError("auth", str(e), retryable=False)
        except APIStatusError as e:
            raise ProviderError("transient" if e.status_code >= 500 else "unavailable", str(e), retryable=e.status_code >= 500)
        except APIConnectionError as e:
            raise ProviderError("transient", str(e))
        text = resp.choices[0].message.content or ""
        units = float(resp.usage.total_tokens) if resp.usage else 0.0
        return Result(data=parse_json(text) if job.schema else {"text": text}, units=units)
