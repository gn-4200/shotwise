import json
import sqlite3
from datetime import date, datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS shots (episode TEXT, id TEXT, scene TEXT, data TEXT, PRIMARY KEY (episode, id));
CREATE TABLE IF NOT EXISTS stage_status (episode TEXT, shot_id TEXT, stage TEXT, status TEXT, note TEXT, updated_at TEXT,
                                         PRIMARY KEY (episode, shot_id, stage));
CREATE TABLE IF NOT EXISTS usage (day TEXT, provider TEXT, units REAL, cost_usd REAL, ok INTEGER, kind TEXT, at TEXT);
CREATE TABLE IF NOT EXISTS approvals (episode TEXT, shot_id TEXT, stage TEXT, decision TEXT, note TEXT, at TEXT);
"""


def _now():
    return datetime.now().isoformat(timespec="seconds")


class SqliteStore:
    def __init__(self, path: Path, limits: dict[str, dict]):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.limits = limits

    def _row(self, r) -> dict:
        row = json.loads(r["data"])
        row.update(episode=r["episode"], scene=r["scene"], stages={})
        for s in self.db.execute("SELECT stage, status, note, updated_at FROM stage_status WHERE episode=? AND shot_id=?",
                                 (r["episode"], r["id"])):
            row["stages"][s["stage"]] = {"status": s["status"], "note": s["note"], "updated_at": s["updated_at"]}
        return row

    def list_episodes(self):
        return [r[0] for r in self.db.execute("SELECT DISTINCT episode FROM shots ORDER BY episode")]

    def upsert_shot(self, episode, shot, scene_id):
        data = {k: v for k, v in shot.items() if k not in ("episode", "scene", "stages")}
        with self.db:
            self.db.execute("INSERT INTO shots (episode, id, scene, data) VALUES (?,?,?,?) "
                            "ON CONFLICT(episode, id) DO UPDATE SET scene=excluded.scene, data=excluded.data",
                            (episode, shot["id"], scene_id, json.dumps(data)))

    def get_shot(self, episode, shot_id):
        r = self.db.execute("SELECT * FROM shots WHERE episode=? AND id=?", (episode, shot_id)).fetchone()
        if r is None:
            raise KeyError(f"{episode}/{shot_id}")
        return self._row(r)

    def list_shots(self, episode):
        return [self._row(r) for r in self.db.execute("SELECT * FROM shots WHERE episode=? ORDER BY id", (episode,))]

    def set_status(self, episode, shot_id, stage, status, note=""):
        with self.db:
            self.db.execute("INSERT OR REPLACE INTO stage_status VALUES (?,?,?,?,?,?)",
                            (episode, shot_id, stage, status, str(note)[:500], _now()))

    def set_field(self, episode, shot_id, key, value):
        row = self.get_shot(episode, shot_id)
        row[key] = value
        self.upsert_shot(episode, row, row["scene"])

    def record_usage(self, provider, units, cost_usd, ok, kind=None):
        with self.db:
            self.db.execute("INSERT INTO usage VALUES (?,?,?,?,?,?,?)",
                            (date.today().isoformat(), provider, units, cost_usd, int(ok), kind, _now()))

    def usage_today(self, provider):
        r = self.db.execute("SELECT COUNT(*), COALESCE(SUM(cost_usd),0) FROM usage WHERE provider=? AND day=? AND ok=1",
                            (provider, date.today().isoformat())).fetchone()
        return r[0], r[1]

    def usage_summary(self, day=None):
        q = ("SELECT provider, COUNT(*) calls, SUM(ok) ok, COUNT(*)-SUM(ok) failed, SUM(units) units, SUM(cost_usd) cost_usd "
             "FROM usage" + (" WHERE day=?" if day else "") + " GROUP BY provider ORDER BY provider")
        return [dict(r) for r in self.db.execute(q, (day,) if day else ())]

    def quota_ok(self, provider):
        per_day = self.limits.get(provider, {}).get("per_day")
        return per_day is None or self.usage_today(provider)[0] < per_day

    def record_approval(self, episode, shot_id, stage, decision, note=""):
        with self.db:
            self.db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?)", (episode, shot_id, stage, decision, note, _now()))

    def list_approvals(self, episode):
        return [dict(r) for r in self.db.execute("SELECT * FROM approvals WHERE episode=? ORDER BY at", (episode,))]
