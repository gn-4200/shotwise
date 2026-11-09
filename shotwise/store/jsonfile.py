import json
import os
import tempfile
from datetime import date, datetime
from pathlib import Path


class JsonStore:
    """One human-readable JSON file, written atomically."""

    def __init__(self, path: Path, limits: dict[str, dict]):
        self.path, self.limits = Path(path), limits
        self._data, self._mtime = None, None
        self._refresh()

    def _refresh(self):
        """Re-read the file when another process (CLI vs review page) changed it."""
        mtime = self.path.stat().st_mtime_ns if self.path.exists() else None
        if self._data is None or mtime != self._mtime:
            self._data = (json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists()
                          else {"shots": {}, "usage": [], "approvals": []})
            self._mtime = mtime

    @property
    def data(self):
        self._refresh()
        return self._data

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)
        os.replace(tmp, self.path)
        self._mtime = self.path.stat().st_mtime_ns

    def list_episodes(self):
        return sorted({row["episode"] for row in self.data["shots"].values()})

    def upsert_shot(self, episode, shot, scene_id):
        row = self.data["shots"].setdefault(f"{episode}/{shot['id']}", {"stages": {}})
        row.update(shot, episode=episode, scene=scene_id)
        self._save()

    def get_shot(self, episode, shot_id):
        return self.data["shots"][f"{episode}/{shot_id}"]

    def list_shots(self, episode):
        return sorted((s for k, s in self.data["shots"].items() if k.startswith(episode + "/")), key=lambda s: s["id"])

    def set_status(self, episode, shot_id, stage, status, note=""):
        self.get_shot(episode, shot_id)["stages"][stage] = {"status": status, "note": str(note)[:500],
                                                            "updated_at": datetime.now().isoformat(timespec="seconds")}
        self._save()

    def set_field(self, episode, shot_id, key, value):
        self.get_shot(episode, shot_id)[key] = value
        self._save()

    def record_usage(self, provider, units, cost_usd, ok, kind=None):
        self.data["usage"].append({"day": date.today().isoformat(), "provider": provider, "units": units,
                                   "cost_usd": cost_usd, "ok": ok, "kind": kind,
                                   "at": datetime.now().isoformat(timespec="seconds")})
        self._save()

    def usage_today(self, provider):
        rows = [u for u in self.data["usage"] if u["provider"] == provider and u["day"] == date.today().isoformat() and u["ok"]]
        return len(rows), sum(u["cost_usd"] for u in rows)

    def usage_summary(self, day=None):
        out = {}
        for u in self.data["usage"]:
            if day and u["day"] != day:
                continue
            s = out.setdefault(u["provider"], {"provider": u["provider"], "calls": 0, "ok": 0, "failed": 0, "units": 0.0, "cost_usd": 0.0})
            s["calls"] += 1
            s["ok" if u["ok"] else "failed"] += 1
            s["units"] += u["units"]
            s["cost_usd"] += u["cost_usd"]
        return sorted(out.values(), key=lambda s: s["provider"])

    def quota_ok(self, provider):
        per_day = self.limits.get(provider, {}).get("per_day")
        return per_day is None or self.usage_today(provider)[0] < per_day

    def record_approval(self, episode, shot_id, stage, decision, note=""):
        self.data["approvals"].append({"episode": episode, "shot_id": shot_id, "stage": stage, "decision": decision,
                                       "note": note, "at": datetime.now().isoformat(timespec="seconds")})
        self._save()

    def list_approvals(self, episode):
        return [a for a in self.data["approvals"] if a["episode"] == episode]
