from shotwise.providers.base import Job, ProviderError, Result
from shotwise.providers.llm._common import parse_json


class ClaudeLLM:
    """Anthropic SDK adapter. Default model Claude Opus 5.5; thinking is adaptive on that model, effort set
    explicitly. Server-side fallback re-runs a classifier-declined request on another Claude model."""

    def __init__(self, name, cfg):
        self.name, self.cfg = name, cfg
        self.model = cfg.model or "claude-opus-5-5"
        self._client = None

    def _client_(self):
        if self._client is None:
            import anthropic
            key = self.cfg.api_key()            # None: the SDK resolves ANTHROPIC_API_KEY or an `ant auth login` profile
            self._client = anthropic.Anthropic(api_key=key) if key else anthropic.Anthropic()
        return self._client

    def healthcheck(self) -> bool:
        try:
            self._client_().models.retrieve(self.model)
            return True
        except Exception:
            return False

    def run(self, job: Job) -> Result:
        import anthropic
        output_config = {"effort": self.cfg.params.get("effort", "medium")}
        if job.schema:
            output_config["format"] = {"type": "json_schema", "schema": job.schema}
        try:
            resp = self._client_().beta.messages.create(
                model=self.model,
                max_tokens=self.cfg.params.get("max_tokens", 16000),
                output_config=output_config,
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                messages=[{"role": "user", "content": job.prompt}],
            )
        except anthropic.RateLimitError as e:
            raise ProviderError("quota", f"claude rate limited: {e.message}")
        except anthropic.AuthenticationError as e:
            raise ProviderError("auth", f"claude auth: {e.message}", retryable=False)
        except anthropic.APIStatusError as e:
            raise ProviderError("transient" if e.status_code >= 500 else "unavailable",
                                f"claude {e.status_code}: {e.message}", retryable=e.status_code >= 500)
        except anthropic.APIConnectionError as e:
            raise ProviderError("transient", f"claude connection: {e}")
        if resp.stop_reason == "refusal":
            raise ProviderError("refusal", "claude declined this request", retryable=False)
        text = next((b.text for b in resp.content if b.type == "text"), "")
        return Result(data=parse_json(text) if job.schema else {"text": text},
                      units=float(resp.usage.input_tokens + resp.usage.output_tokens))
