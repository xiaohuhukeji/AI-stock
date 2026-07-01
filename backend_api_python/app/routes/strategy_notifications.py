"""Strategy notification routes."""
import json
from datetime import timezone as dt_tz, datetime
import traceback
import time
from zoneinfo import ZoneInfo

from flask import g, jsonify, request

from app.routes.strategy_blueprint import strategy_blp
from app.utils.auth import login_required
from app.utils.db import get_db_connection
from app.utils.logger import get_logger


logger = get_logger(__name__)


def _current_user_strategy_ids(user_id: int) -> list[int]:
    with get_db_connection() as db:
        cur = db.cursor()
        cur.execute("SELECT id FROM qd_strategies_trading WHERE user_id = ?", (user_id,))
        rows = cur.fetchall() or []
        cur.close()
    return [r.get('id') for r in rows if r.get('id')]


def _user_notification_scope(user_id: int, strategy_id: int | None = None) -> tuple[list[str], list]:
    user_strategy_ids = _current_user_strategy_ids(user_id)
    where: list[str] = []
    args: list = []

    if strategy_id:
        if strategy_id in user_strategy_ids:
            where.append("strategy_id = ?")
            args.append(int(strategy_id))
        else:
            where.append("1 = 0")
        return where, args

    if user_strategy_ids:
        placeholders = ",".join(["?"] * len(user_strategy_ids))
        where.append(f"(strategy_id IN ({placeholders}) OR (strategy_id IS NULL AND user_id = ?))")
        args.extend(user_strategy_ids)
        args.append(user_id)
    else:
        where.append("strategy_id IS NULL AND user_id = ?")
        args.append(user_id)
    return where, args


@strategy_blp.route('/strategies/notifications', methods=['GET'])
@login_required
def get_strategy_notifications():
    """Strategy signal notifications for the current user."""
    try:
        user_id = g.user_id
        strategy_id = request.args.get('id', type=int)
        limit = request.args.get('limit', type=int) or 50
        limit = max(1, min(200, int(limit)))
        since_id = request.args.get('since_id', type=int) or 0

        where, args = _user_notification_scope(user_id, strategy_id)
        if since_id:
            where.append("id > ?")
            args.append(int(since_id))
        where_sql = "WHERE " + " AND ".join(where)

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"""
                SELECT *
                FROM qd_strategy_notifications
                {where_sql}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(args + [int(limit)]),
            )
            rows = cur.fetchall() or []
            cur.close()

        processed_rows = []
        for row in rows:
            item = dict(row)
            created_at = item.get('created_at')
            if created_at:
                if hasattr(created_at, 'timestamp'):
                    if getattr(created_at, 'tzinfo', None) is None:
                        created_at = created_at.replace(tzinfo=dt_tz.utc)
                    item['created_at'] = int(created_at.timestamp())
                elif isinstance(created_at, str):
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        item['created_at'] = int(dt.timestamp())
                    except Exception:
                        pass
            processed_rows.append(item)

        return jsonify({'code': 1, 'msg': 'success', 'data': {'items': processed_rows}})
    except Exception as e:
        logger.error(f"get_strategy_notifications failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 0, 'msg': str(e), 'data': {'items': []}}), 500


@strategy_blp.route('/strategies/notifications/unread-count', methods=['GET'])
@login_required
def get_unread_notification_count():
    """Get unread notification count for the current user."""
    try:
        user_id = g.user_id
        where, args = _user_notification_scope(user_id)
        where.insert(0, "is_read = 0")
        where_sql = "WHERE " + " AND ".join(where)

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                f"SELECT COUNT(1) AS cnt FROM qd_strategy_notifications {where_sql}",
                tuple(args),
            )
            cnt = int((cur.fetchone() or {}).get("cnt") or 0)
            cur.close()

        return jsonify({'code': 1, 'msg': 'success', 'data': {'unread': cnt}})
    except Exception as e:
        logger.error(f"get_unread_notification_count failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 0, 'msg': str(e), 'data': {'unread': 0}}), 500


@strategy_blp.route('/strategies/notifications/read', methods=['POST'])
@login_required
def mark_notification_read():
    """Mark a single notification as read for the current user."""
    try:
        user_id = g.user_id
        data = request.get_json(force=True, silent=True) or {}
        notification_id = data.get('id')
        if not notification_id:
            return jsonify({'code': 0, 'msg': 'Missing id'}), 400

        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE qd_strategy_notifications SET is_read = 1
                WHERE id = ? AND (
                    strategy_id IN (SELECT id FROM qd_strategies_trading WHERE user_id = ?)
                    OR (strategy_id IS NULL AND user_id = ?)
                )
                """,
                (int(notification_id), user_id, user_id)
            )
            db.commit()
            cur.close()

        return jsonify({'code': 1, 'msg': 'success'})
    except Exception as e:
        logger.error(f"mark_notification_read failed: {str(e)}")
        return jsonify({'code': 0, 'msg': str(e)}), 500


@strategy_blp.route('/strategies/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """Mark all notifications as read for the current user."""
    try:
        user_id = g.user_id
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                UPDATE qd_strategy_notifications SET is_read = 1
                WHERE strategy_id IN (SELECT id FROM qd_strategies_trading WHERE user_id = ?)
                   OR (strategy_id IS NULL AND user_id = ?)
                """,
                (user_id, user_id)
            )
            db.commit()
            cur.close()

        return jsonify({'code': 1, 'msg': 'success'})
    except Exception as e:
        logger.error(f"mark_all_notifications_read failed: {str(e)}")
        return jsonify({'code': 0, 'msg': str(e)}), 500


@strategy_blp.route('/strategies/notifications/clear', methods=['DELETE'])
@login_required
def clear_notifications():
    """Clear all notifications for the current user."""
    try:
        user_id = g.user_id
        with get_db_connection() as db:
            cur = db.cursor()
            cur.execute(
                """
                DELETE FROM qd_strategy_notifications
                WHERE strategy_id IN (SELECT id FROM qd_strategies_trading WHERE user_id = ?)
                   OR (strategy_id IS NULL AND user_id = ?)
                """,
                (user_id, user_id)
            )
            db.commit()
            cur.close()

        return jsonify({'code': 1, 'msg': 'success'})
    except Exception as e:
        logger.error(f"clear_notifications failed: {str(e)}")
        return jsonify({'code': 0, 'msg': str(e)}), 500


@strategy_blp.route('/strategies/notifications/manual-alert', methods=['POST'])
@login_required
def send_manual_alert_notification():
    """Send manual operation alert notification (e.g., A-share pre-market price reminder).

    Request body:
        strategy_id: int (optional)
        symbol: str
        price: float
        session: str (e.g., "上午盘", "下午盘")
        alert_time: str (optional)
    """
    try:
        from app.services.signal_notifier import SignalNotifier

        user_id = g.user_id
        data = request.get_json(force=True, silent=True) or {}
        strategy_id = data.get('strategy_id')
        symbol = (data.get('symbol') or '').strip()
        price = float(data.get('price') or 0)
        session = (data.get('session') or '').strip()
        alert_time = (data.get('alert_time') or '').strip()

        if not symbol:
            return jsonify({'code': 0, 'msg': 'Missing symbol'}), 400
        if price <= 0:
            return jsonify({'code': 0, 'msg': 'Invalid price'}), 400

        strategy_name = ''
        channels = ['browser']
        targets = {}

        with get_db_connection() as db:
            cur = db.cursor()

            if strategy_id:
                cur.execute(
                    "SELECT strategy_name, notification_config FROM qd_strategies_trading WHERE id = ? AND user_id = ?",
                    (int(strategy_id), user_id)
                )
                row = cur.fetchone()
                if row:
                    strategy_name = row.get('strategy_name') or ''
                    notif_cfg_str = row.get('notification_config') or ''
                    if notif_cfg_str:
                        try:
                            notif_cfg = json.loads(notif_cfg_str)
                            channels = notif_cfg.get('channels') or ['browser']
                            targets = notif_cfg.get('targets') or {}
                        except Exception:
                            pass

            cur.execute("SELECT notification_settings, email, language FROM qd_users WHERE id = ?", (user_id,))
            user_row = cur.fetchone()
            cur.close()

        if user_row:
            user_settings_str = user_row.get('notification_settings') or ''
            account_email = (user_row.get('email') or '').strip()
            language = (user_row.get('language') or 'zh-CN').strip()
            if user_settings_str:
                try:
                    user_settings = json.loads(user_settings_str)
                    if not targets.get('email'):
                        notify_email = (user_settings.get('email') or '').strip() or account_email
                        targets['email'] = notify_email
                    if not targets.get('telegram'):
                        targets['telegram'] = (user_settings.get('telegram_chat_id') or '').strip()
                    targets['telegram_bot_token'] = (user_settings.get('telegram_bot_token') or '').strip()
                    if not targets.get('phone'):
                        targets['phone'] = (user_settings.get('phone') or '').strip()
                    if not targets.get('discord'):
                        targets['discord'] = (user_settings.get('discord_webhook') or '').strip()
                    if not targets.get('webhook'):
                        targets['webhook'] = (user_settings.get('webhook_url') or '').strip()
                    targets['webhook_token'] = (user_settings.get('webhook_token') or '').strip()
                    targets['webhook_signing_secret'] = (user_settings.get('webhook_signing_secret') or '').strip()
                except Exception:
                    pass
            else:
                if account_email and not targets.get('email'):
                    targets['email'] = account_email
        else:
            language = 'zh-CN'

        zh = language.lower().startswith('zh')

        session_label = session or ('交易时段' if zh else 'trading session')
        title = (
            f"【手动操作提示】{symbol} {session_label}即将开始"
            if zh else
            f"[Manual Alert] {symbol} {session_label} starting soon"
        )

        now = int(time.time())
        try:
            time_display = datetime.fromtimestamp(now, tz=ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            time_display = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        message_lines = []
        if zh:
            message_lines.append(f"标的：{symbol}")
            if strategy_name:
                message_lines.append(f"策略：{strategy_name}")
            message_lines.append(f"当前价格：{price:.2f}")
            message_lines.append(f"交易时段：{session_label}")
            message_lines.append(f"提醒时间：{alert_time or time_display}")
            message_lines.append("")
            message_lines.append("建议提前下单，避免开盘价波动影响成交。")
        else:
            message_lines.append(f"Symbol: {symbol}")
            if strategy_name:
                message_lines.append(f"Strategy: {strategy_name}")
            message_lines.append(f"Current Price: {price:.2f}")
            message_lines.append(f"Session: {session_label}")
            message_lines.append(f"Alert Time: {alert_time or time_display}")
            message_lines.append("")
            message_lines.append("Consider placing orders early to avoid opening price volatility.")

        message_plain = "\n".join(message_lines)

        html_lines = [f"<p><strong>{title}</strong></p>"]
        for line in message_lines:
            if line:
                html_lines.append(f"<p>{line}</p>")
            else:
                html_lines.append("<br/>")
        message_html = "\n".join(html_lines)

        notifier = SignalNotifier()
        results = {}

        for ch in channels:
            c = (ch or '').strip().lower()
            if not c:
                continue
            try:
                if c == 'browser':
                    payload = {
                        'event': 'manual_alert',
                        'strategy': {
                            'id': int(strategy_id) if strategy_id else 0,
                            'name': strategy_name
                        },
                        'instrument': {
                            'symbol': symbol
                        },
                        'signal': {
                            'type': 'manual_alert',
                            'action': 'alert',
                            'side': 'long'
                        },
                        'order': {
                            'ref_price': price
                        },
                        'extra': {
                            'session': session,
                            'alert_time': alert_time or time_display
                        }
                    }
                    ok, err = notifier._notify_browser(
                        strategy_id=int(strategy_id) if strategy_id else 0,
                        symbol=symbol,
                        signal_type='manual_alert',
                        channels=channels,
                        title=title,
                        message=message_plain,
                        payload=payload,
                    )
                elif c == 'email':
                    to_email = (targets.get('email') or '').strip()
                    ok, err = notifier._notify_email(
                        to_email=to_email,
                        subject=title,
                        body_text=message_plain,
                        body_html=message_html,
                    )
                elif c == 'telegram':
                    chat_id = (targets.get('telegram') or '').strip()
                    token_override = (targets.get('telegram_bot_token') or '').strip()
                    telegram_text = f"<b>{title}</b>\n\n" + "\n".join(
                        [line for line in message_lines if line]
                    )
                    ok, err = notifier._notify_telegram(
                        chat_id=chat_id,
                        text=telegram_text,
                        token_override=token_override,
                        parse_mode="HTML",
                    )
                elif c == 'discord':
                    url = (targets.get('discord') or '').strip()
                    payload = {
                        'event': 'manual_alert',
                        'strategy': {'name': strategy_name},
                        'instrument': {'symbol': symbol},
                        'price': price,
                        'session': session,
                    }
                    ok, err = notifier._notify_discord(
                        url=url,
                        payload=payload,
                        fallback_text=message_plain,
                    )
                elif c == 'webhook':
                    url = (targets.get('webhook') or '').strip()
                    payload = {
                        'event': 'manual_alert',
                        'strategy_id': strategy_id,
                        'strategy_name': strategy_name,
                        'symbol': symbol,
                        'price': price,
                        'session': session,
                        'alert_time': alert_time or time_display,
                    }
                    ok, err = notifier._notify_webhook(
                        url=url,
                        payload=payload,
                        token_override=targets.get('webhook_token'),
                        headers_override=None,
                        signing_secret_override=targets.get('webhook_signing_secret'),
                    )
                elif c == 'phone':
                    to_phone = (targets.get('phone') or '').strip()
                    ok, err = notifier._notify_phone(
                        to_phone=to_phone,
                        body=message_plain,
                    )
                else:
                    ok, err = False, f"unsupported_channel:{c}"
            except Exception as e:
                ok, err = False, str(e)

            results[c] = {'ok': bool(ok), 'error': (err or '')}

        any_ok = any((v or {}).get('ok') for v in results.values())
        failed = [k for k, v in results.items() if not (v or {}).get('ok')]

        if not any_ok and results:
            detail = '; '.join(f"{k}: {(results[k] or {}).get('error', '')}" for k in failed) or 'all channels failed'
            return jsonify({'code': 0, 'msg': detail, 'data': {'results': results}})

        msg = 'Manual alert sent'
        if failed:
            msg = f"Sent OK; failed: {', '.join(failed)}"
        return jsonify({'code': 1, 'msg': msg, 'data': {'results': results}})
    except Exception as e:
        logger.error(f"send_manual_alert_notification failed: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'code': 0, 'msg': str(e)}), 500
