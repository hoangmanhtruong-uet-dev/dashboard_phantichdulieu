import json
from pathlib import Path

from data.database import connection


class AnalyticsRepository:
    def __init__(self, database_path: Path | str):
        self.database_path = database_path

    def events(self, workspace_id: int, start: str, end: str) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT event_id,user_id,session_id,event_name,occurred_at,revenue,
                          source,device,region,product
                   FROM analytics_events
                   WHERE workspace_id=? AND occurred_at>=? AND occurred_at<=?
                   ORDER BY occurred_at,id""",
                (workspace_id, start, end),
            ).fetchall()
            return [dict(row) for row in rows]

    def all_events(self, workspace_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT event_id,user_id,session_id,event_name,occurred_at,revenue,
                          source,device,region,product
                   FROM analytics_events WHERE workspace_id=? ORDER BY occurred_at,id""",
                (workspace_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def latest_event_at(self, workspace_id: int) -> str | None:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT MAX(occurred_at) latest FROM analytics_events WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
            return row["latest"] if row else None

    def create_segment(
        self,
        workspace_id: int,
        user_id: int,
        name: str,
        match_type: str,
        rules: list[dict],
    ) -> dict:
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                """INSERT INTO analytics_segments
                   (workspace_id,name,match_type,rules_json,created_by,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (workspace_id, name, match_type, json.dumps(rules), user_id, now, now),
            )
            row = conn.execute(
                "SELECT * FROM analytics_segments WHERE id=? AND workspace_id=?",
                (cursor.lastrowid, workspace_id),
            ).fetchone()
            result = dict(row)
            result["rules"] = json.loads(result.pop("rules_json"))
            return result

    def list_segments(self, workspace_id: int) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                "SELECT * FROM analytics_segments WHERE workspace_id=? ORDER BY updated_at DESC",
                (workspace_id,),
            ).fetchall()
            result = []
            for row in rows:
                item = dict(row)
                item["rules"] = json.loads(item.pop("rules_json"))
                result.append(item)
            return result
