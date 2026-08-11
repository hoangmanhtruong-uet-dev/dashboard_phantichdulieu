from datetime import datetime
from pathlib import Path

from data.database import connection


def seed_demo_records(database_path: Path) -> None:
    """Seed UI support records only when explicitly enabled by configuration."""
    now = datetime.now().isoformat(timespec="seconds")
    with connection(database_path) as conn:
        if conn.execute("SELECT COUNT(*) FROM insights").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO insights (insight_type,title,description,change_value,severity,created_at) VALUES (?,?,?,?,?,?)",
                [
                    (
                        "opportunity",
                        "Organic Search tăng trưởng",
                        "Lưu lượng Organic Search cao hơn mức dự kiến trong 7 ngày qua.",
                        "+23%",
                        "success",
                        now,
                    ),
                    (
                        "warning",
                        "Chuyển đổi Mobile giảm",
                        "Tỷ lệ hoàn tất checkout trên Mobile đang thấp hơn mức trung bình.",
                        "-12%",
                        "warning",
                        now,
                    ),
                    (
                        "opportunity",
                        "Campaign Summer Sale",
                        "Chiến dịch có tiềm năng ROI cao nếu tăng ngân sách trong 5 ngày tới.",
                        "High ROI",
                        "success",
                        now,
                    ),
                    (
                        "audience",
                        "Nhóm khách hàng từ Google",
                        "Khách Organic có tỷ lệ quay lại trong 30 ngày cao hơn các kênh khác.",
                        "+34%",
                        "info",
                        now,
                    ),
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO alerts (title,description,severity,is_read,created_at) VALUES (?,?,?,?,?)",
                [
                    (
                        "Doanh thu giảm bất thường",
                        "Paid Social thấp hơn 21% so với mức trung bình.",
                        "high",
                        0,
                        now,
                    ),
                    (
                        "Ngân sách Ads sắp đạt ngưỡng",
                        "Facebook Ads đã sử dụng 82% ngân sách tháng.",
                        "medium",
                        0,
                        now,
                    ),
                    (
                        "Conversion đã phục hồi",
                        "Tỷ lệ chuyển đổi tăng lại sau khi tối ưu landing page.",
                        "success",
                        1,
                        now,
                    ),
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO reports (name,report_type,status,updated_at) VALUES (?,?,?,?)",
                [
                    ("Báo cáo hiệu suất Q3", "performance", "ready", now),
                    ("Dự báo doanh thu tháng 11", "forecast", "ready", now),
                    ("Phân tích Cohort 2026", "cohort", "draft", now),
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM data_sources").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO data_sources (name,source_type,status,last_sync) VALUES (?,?,?,?)",
                [
                    ("Google Analytics", "analytics", "connected", now),
                    ("Facebook Ads", "advertising", "warning", now),
                    ("Sales Database", "database", "connected", now),
                ],
            )
        if conn.execute("SELECT COUNT(*) FROM saved_views").fetchone()[0] == 0:
            conn.executemany(
                "INSERT INTO saved_views (name,description,view_type,is_favorite) VALUES (?,?,?,?)",
                [
                    (
                        "Lưu lượng Mobile Việt Nam",
                        "Traffic · Mobile · 7 ngày",
                        "traffic",
                        1,
                    ),
                    (
                        "Hiệu suất Marketing",
                        "Revenue · Campaign · 30 ngày",
                        "revenue",
                        1,
                    ),
                    ("Người dùng mới", "New users · Acquisition", "users", 0),
                    ("Checkout Funnel", "Conversion · Funnel", "funnel", 1),
                ],
            )
        conn.execute(
            "INSERT OR IGNORE INTO user_profile (id,full_name,job_title,email,phone,workspace) VALUES (1,?,?,?,?,?)",
            ("Trương Anh", "Data Analyst", "truong@nexus.vn", "", "Nexus Team"),
        )
