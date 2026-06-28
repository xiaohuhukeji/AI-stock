"""Kronos AI prediction endpoints — R-class market data extension."""
from __future__ import annotations

import pandas as pd

from app.services.kline import KlineService
from app.services.kronos_service import KronosService
from app.utils.agent_auth import (
    SCOPE_R, agent_required, instrument_allowed, market_allowed,
)
from app.utils.logger import get_logger
from flask import request

from . import agent_v1_bp
from ._helpers import clip_int, envelope, error

logger = get_logger(__name__)
_kline_service = KlineService()


@agent_v1_bp.route("/kronos/predict", methods=["GET"])
@agent_required(SCOPE_R)
def kronos_predict():
    """Generate stock price predictions using Kronos foundation model.

    Query params:
        market, symbol     (required)
        timeframe          (default 1D)
        lookback           60..512 (default 400) — historical periods to use
        pred_len           1..240 (default 120) — future periods to predict
        T                  0.1..2.0 (default 1.0) — temperature for sampling
        top_p              0.1..1.0 (default 0.9) — nucleus sampling probability
        apply_price_limit  true/false (default true) — apply ±10% price limits
    """
    market = (request.args.get("market") or "").strip()
    symbol = (request.args.get("symbol") or "").strip()
    timeframe = (request.args.get("timeframe") or "1D").strip()
    lookback = clip_int(request.args.get("lookback"), default=400, lo=60, hi=512)
    pred_len = clip_int(request.args.get("pred_len"), default=120, lo=1, hi=240)

    T_raw = request.args.get("T") or request.args.get("temperature")
    try:
        T = float(T_raw) if T_raw else 1.0
        T = max(0.1, min(2.0, T))
    except ValueError:
        T = 1.0

    top_p_raw = request.args.get("top_p") or request.args.get("nucleus_prob")
    try:
        top_p = float(top_p_raw) if top_p_raw else 0.9
        top_p = max(0.1, min(1.0, top_p))
    except ValueError:
        top_p = 0.9

    apply_price_limit = request.args.get("apply_price_limit", "true").lower() == "true"

    if not market or not symbol:
        return error(400, "market and symbol are required")
    if not market_allowed(market):
        return error(403, f"Market not allowed: {market}", http=403)
    if not instrument_allowed(symbol):
        return error(403, f"Instrument not allowed: {symbol}", http=403)

    try:
        logger.info(f"Kronos prediction request: {market}/{symbol} timeframe={timeframe}")

        rows = _kline_service.get_kline(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            limit=lookback + pred_len,
        ) or []

        if len(rows) < lookback:
            return error(400, f"Insufficient data: need {lookback} rows, got {len(rows)}")

        df = pd.DataFrame(rows)

        if "datetime" in df.columns:
            df["date"] = pd.to_datetime(df["datetime"])
        elif "timestamps" in df.columns:
            df["date"] = pd.to_datetime(df["timestamps"])

        col_mapping = {"c": "close", "o": "open", "h": "high", "l": "low", "v": "volume"}
        df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

        required = ["open", "high", "low", "close"]
        missing = [c for c in required if c not in df.columns]
        if missing:
            return error(500, f"Kline data missing columns: {missing}", http=502)

        kronos = KronosService()
        pred_df = kronos.predict(
            df=df,
            pred_len=pred_len,
            lookback=lookback,
            T=T,
            top_p=top_p,
        )

        if apply_price_limit and market == "CNStock":
            last_close = df["close"].iloc[-1]
            pred_df = kronos.apply_price_limits(pred_df, last_close)

        summary = kronos.get_prediction_summary(df, pred_df)

        predictions = []
        for _, row in pred_df.iterrows():
            predictions.append({
                "date": row["date"].isoformat() if hasattr(row["date"], "isoformat") else str(row["date"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]) if "volume" in row else 0,
                "amount": float(row["amount"]) if "amount" in row else 0,
            })

        return envelope({
            "market": market,
            "symbol": symbol,
            "timeframe": timeframe,
            "lookback": lookback,
            "pred_len": pred_len,
            "summary": summary,
            "predictions": predictions,
        })

    except Exception as exc:
        logger.error(f"Kronos prediction failed: {exc}", exc_info=True)
        return error(500, "Kronos prediction failed", details=str(exc), retriable=True, http=502)


@agent_v1_bp.route("/kronos/health", methods=["GET"])
@agent_required(SCOPE_R)
def kronos_health():
    """Check if Kronos model is available."""
    try:
        from app.services.kronos_service import _KRONOS_LOADED
        return envelope({
            "available": _KRONOS_LOADED,
            "message": "Kronos model loaded successfully" if _KRONOS_LOADED else "Kronos model not yet loaded",
        })
    except Exception as exc:
        logger.error(f"Kronos health check failed: {exc}")
        return envelope({
            "available": False,
            "message": str(exc),
        })