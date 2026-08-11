from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from data.database import connection


RESOURCE_COLUMNS: dict[str, dict[str, Any]] = {
    "insights": {
        "sort": {"id", "created_at", "title", "severity"},
        "search": {"title", "description", "insight_type"},
        "filter": {"severity", "insight_type"},
        "date": "created_at",
    },
    "alerts": {
        "sort": {"id", "created_at", "title", "severity", "is_read"},
        "search": {"title", "description"},
        "filter": {"severity", "is_read"},
        "date": "created_at",
    },
    "reports": {
        "sort": {"id", "updated_at", "name", "status", "report_type"},
        "search": {"name", "report_type"},
        "filter": {"status", "report_type"},
        "date": "updated_at",
    },
    "data_sources": {
        "sort": {
            "id",
            "name",
            "status",
            "source_type",
            "last_sync",
            "last_import_at",
            "event_count",
            "health_status",
        },
        "search": {"name", "source_type"},
        "filter": {"status", "source_type", "health_status"},
        "date": "last_sync",
    },
    "saved_views": {
        "sort": {"id", "name", "view_type", "is_favorite"},
        "search": {"name", "description", "view_type"},
        "filter": {"view_type", "is_favorite"},
        "date": None,
    },
}


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class NexusRepository:
    def __init__(self, database_path: Path):
        self.database_path = database_path

    def table_exists(self, table_name: str) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                ).fetchone()
                is not None
            )

    def latest_order_date(self, workspace_id: int) -> Optional[str]:
        with connection(self.database_path) as conn:
            row = conn.execute(
                "SELECT MAX(order_date) AS latest FROM orders WHERE workspace_id=?",
                (workspace_id,),
            ).fetchone()
            return row["latest"] if row else None

    def period_stats(self, workspace_id: int, start: datetime, end: datetime) -> dict:
        with connection(self.database_path) as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(amount),0) AS revenue, COUNT(*) AS orders_count,
                          COUNT(DISTINCT customer_id) AS users_count, COALESCE(AVG(amount),0) AS average_order
                   FROM orders WHERE workspace_id=? AND datetime(order_date) BETWEEN datetime(?) AND datetime(?)""",
                (workspace_id, start.isoformat(sep=" "), end.isoformat(sep=" ")),
            ).fetchone()
            return dict(row)

    def recent_orders(self, workspace_id: int, limit: int = 1000) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                "SELECT order_id,customer_id,category,region,amount,order_date FROM orders WHERE workspace_id=? ORDER BY order_date DESC LIMIT ?",
                (workspace_id, limit),
            ).fetchall()
            return [dict(row) for row in rows]

    def recent_region_amounts(self, workspace_id: int, limit: int = 500) -> list[tuple]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                "SELECT region,amount FROM orders WHERE workspace_id=? ORDER BY order_date DESC LIMIT ?",
                (workspace_id, limit),
            ).fetchall()
            return [(row["region"], row["amount"]) for row in rows]

    def daily_revenue(
        self, workspace_id: int, start: datetime, end: datetime
    ) -> list[dict]:
        with connection(self.database_path) as conn:
            rows = conn.execute(
                """SELECT date(order_date) AS label, ROUND(SUM(amount),2) AS value, COUNT(*) AS orders
                   FROM orders WHERE workspace_id=? AND datetime(order_date) BETWEEN datetime(?) AND datetime(?)
                   GROUP BY date(order_date) ORDER BY date(order_date)""",
                (workspace_id, start.isoformat(sep=" "), end.isoformat(sep=" ")),
            ).fetchall()
            return [dict(row) for row in rows]

    def revenue_grouped(
        self, workspace_id: int, column: str, start: datetime, end: datetime
    ) -> list[dict]:
        if column not in {"region", "category"}:
            raise ValueError("Unsupported revenue grouping")
        with connection(self.database_path) as conn:
            rows = conn.execute(
                f"""SELECT {column} AS name, ROUND(SUM(amount),2) AS revenue, COUNT(*) AS orders
                    FROM orders WHERE workspace_id=? AND datetime(order_date) BETWEEN datetime(?) AND datetime(?)
                    GROUP BY {column} ORDER BY revenue DESC""",
                (workspace_id, start.isoformat(sep=" "), end.isoformat(sep=" ")),
            ).fetchall()
            return [dict(row) for row in rows]

    def count_unread_alerts(self, workspace_id: int) -> int:
        with connection(self.database_path) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM alerts WHERE workspace_id=? AND is_read=0",
                (workspace_id,),
            ).fetchone()[0]

    def list_rows(
        self,
        table: str,
        workspace_id: int,
        *,
        order_by: str = "id",
        limit: Optional[int] = None,
        where: str = "",
        params: tuple = (),
    ) -> list[dict]:
        allowed = {
            "insights": {"id", "created_at"},
            "alerts": {"id", "created_at"},
            "reports": {"id", "updated_at"},
            "data_sources": {"id"},
            "saved_views": {"id", "is_favorite"},
        }
        if table not in allowed or order_by not in allowed[table]:
            raise ValueError("Unsupported repository query")
        query = f"SELECT * FROM {table} WHERE workspace_id=?"
        scoped_params: tuple[object, ...] = (workspace_id,)
        if where:
            query += f" AND ({where})"
            scoped_params += params
        query += f" ORDER BY {order_by} DESC"
        if limit is not None:
            query += " LIMIT ?"
            scoped_params += (limit,)
        with connection(self.database_path) as conn:
            return [dict(row) for row in conn.execute(query, scoped_params).fetchall()]

    def query_rows(
        self,
        table: str,
        workspace_id: int,
        *,
        page: int,
        page_size: int,
        search: str = "",
        filters: Optional[dict[str, object]] = None,
        sort_by: str = "id",
        sort_order: str = "desc",
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> tuple[list[dict], int]:
        config = RESOURCE_COLUMNS.get(table)
        if (
            not config
            or sort_by not in config["sort"]
            or sort_order
            not in {
                "asc",
                "desc",
            }
        ):
            raise ValueError("Unsupported repository query")
        clauses = ["workspace_id=?"]
        params: list[object] = [workspace_id]
        if search:
            term = f"%{_escape_like(search)}%"
            search_columns = sorted(config["search"])
            clauses.append(
                "("
                + " OR ".join(
                    f"{column} LIKE ? ESCAPE '\\'" for column in search_columns
                )
                + ")"
            )
            params.extend(term for _ in search_columns)
        for column, value in (filters or {}).items():
            if column not in config["filter"]:
                raise ValueError("Unsupported resource filter")
            if value is not None and value != "":
                clauses.append(f"{column}=?")
                params.append(value)
        date_column = config["date"]
        if date_from and date_column:
            clauses.append(f"date({date_column})>=date(?)")
            params.append(date_from)
        if date_to and date_column:
            clauses.append(f"date({date_column})<=date(?)")
            params.append(date_to)
        where = " AND ".join(clauses)
        with connection(self.database_path) as conn:
            total = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where}", tuple(params)
            ).fetchone()[0]
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE {where} ORDER BY {sort_by} {sort_order.upper()}, id {sort_order.upper()} LIMIT ? OFFSET ?",
                (*params, page_size, (page - 1) * page_size),
            ).fetchall()
            return [dict(row) for row in rows], total

    def create_alert(self, workspace_id: int, values: tuple) -> dict:
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                "INSERT INTO alerts (title,description,severity,is_read,created_at,workspace_id) VALUES (?,?,?,?,?,?)",
                (*values, workspace_id),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM alerts WHERE id=?", (cursor.lastrowid,)
                ).fetchone()
            )

    def mark_alert_read(self, workspace_id: int, alert_id: int) -> bool:
        with connection(self.database_path) as conn:
            return (
                conn.execute(
                    "UPDATE alerts SET is_read=1 WHERE id=? AND workspace_id=?",
                    (alert_id, workspace_id),
                ).rowcount
                > 0
            )

    def create_report(self, workspace_id: int, values: tuple) -> dict:
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                "INSERT INTO reports (name,report_type,status,updated_at,workspace_id) VALUES (?,?,?,?,?)",
                (*values, workspace_id),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM reports WHERE id=?", (cursor.lastrowid,)
                ).fetchone()
            )

    def create_data_source(self, workspace_id: int, values: tuple) -> dict:
        with connection(self.database_path) as conn:
            cursor = conn.execute(
                "INSERT INTO data_sources (name,source_type,status,last_sync,workspace_id) VALUES (?,?,?,?,?)",
                (*values, workspace_id),
            )
            return dict(
                conn.execute(
                    "SELECT * FROM data_sources WHERE id=?", (cursor.lastrowid,)
                ).fetchone()
            )

    def get_profile(self) -> Optional[dict]:
        with connection(self.database_path) as conn:
            row = conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
            return dict(row) if row else None

    def update_profile(self, values: tuple) -> dict:
        with connection(self.database_path) as conn:
            conn.execute(
                "UPDATE user_profile SET full_name=?,job_title=?,email=?,phone=?,workspace=? WHERE id=1",
                values,
            )
            return dict(
                conn.execute("SELECT * FROM user_profile WHERE id=1").fetchone()
            )
