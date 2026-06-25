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


def append_strategy_log(strategy_id: int, level: str, message: str, reference_price: float = 0) -> None:
    """Best-effort insert; never raises to caller."""
    try:
        sid = int(strategy_id)
        lv = (level or "info").strip().lower()[:20]
        msg = str(message or "").strip()
        if not msg:
            return
        msg = msg[:8000]
        ref_price = float(reference_price) if reference_price else 0
        max_logs = _get_max_logs_per_strategy()
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                INSERT INTO qd_strategy_logs (strategy_id, level, message, timestamp, reference_price)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (sid, lv, msg, datetime.now(timezone.utc), ref_price),
            )
            cur.execute(
                """
                DELETE FROM qd_strategy_logs
                WHERE strategy_id = %s AND id NOT IN (
                    SELECT id FROM qd_strategy_logs
                    WHERE strategy_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                )
                """,
                (sid, sid, max_logs),
            )
            db.commit()
            cur.close()
    except Exception as e:
        logger.debug("append_strategy_log skip: %s", e)
