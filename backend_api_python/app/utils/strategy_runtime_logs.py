"""Persist strategy runtime lines for the strategy management UI (`qd_strategy_logs`)."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.utils.db import get_db_connection
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _get_max_logs_per_strategy() -> int:
    """获取每个策略的最大日志数量（默认500条）"""
    try:
        v = os.getenv("STRATEGY_LOG_MAX_COUNT")
        return int(v) if v else 500
    except (ValueError, TypeError):
        return 500


def append_strategy_log(strategy_id: int, level: str, message: str) -> None:
    """Best-effort insert; never raises to caller."""
    try:
        sid = int(strategy_id)
        lv = (level or "info").strip().lower()[:20]
        msg = str(message or "").strip()
        if not msg:
            return
        msg = msg[:8000]
        max_logs = _get_max_logs_per_strategy()
        with get_db_connection() as db:
            cur = db.cursor()
            # 插入新日志
            cur.execute(
                """
                INSERT INTO qd_strategy_logs (strategy_id, level, message, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (sid, lv, msg, datetime.now(timezone.utc)),
            )
            # 自动清理旧日志（保留最新的 max_logs 条）
            cur.execute(
                """
                DELETE FROM qd_strategy_logs
                WHERE strategy_id = ? AND id NOT IN (
                    SELECT id FROM qd_strategy_logs
                    WHERE strategy_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                )
                """,
                (sid, sid, max_logs),
            )
            db.commit()
            cur.close()
    except Exception as e:
        logger.debug("append_strategy_log skip: %s", e)
