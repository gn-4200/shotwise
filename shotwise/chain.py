import logging

from shotwise.providers.base import Deferred, Job, ManualRequired, Provider, ProviderError, Result

log = logging.getLogger("shotwise.chain")


class StageBlocked(Exception):
    """Every provider in the chain failed and none was manual."""


def run_chain(providers: list[Provider], job: Job, store, attempts: int = 1, qc=None) -> Result:
    errors: list[str] = []
    for p in providers:
        if not store.quota_ok(p.name):
            errors.append(f"{p.name}: daily quota reached")
            continue
        for attempt in range(1, attempts + 1):
            job.params["attempt"] = attempt
            try:
                result = p.run(job)
                if qc is not None:
                    qc(result, job)                           # raises ProviderError("qc_failed") when it fails
                store.record_usage(p.name, units=result.units, cost_usd=result.cost_usd, ok=True)
                result.provider = p.name
                return result
            except (ManualRequired, Deferred):
                raise                                         # a human or a remote worker finishes this job
            except ProviderError as e:
                store.record_usage(p.name, units=0, cost_usd=0, ok=False, kind=e.kind)
                errors.append(f"{p.name} attempt {attempt}: {e}")
                log.info("%s failed: %s", p.name, e)        # recorded in the ledger and the status note
                if not e.retryable:
                    break                                     # auth, quota, unavailable, refusal: next provider
    raise StageBlocked(f"stage '{job.stage}' exhausted its chain:\n  " + "\n  ".join(errors))
