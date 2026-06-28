"""Kronos AI prediction API routes — for frontend (human user) access."""
from __future__ import annotations

import pandas as pd

from app.openapi.blueprint import HumanBlueprint as Blueprint
from app.services.kline import KlineService
from app.services.kronos_service import KronosService, _KRONOS_LOADED, _KRONOS_CONFIG, _current_model_name
from app.utils.auth import login_required
from app.utils.logger import get_logger
from flask import jsonify, request

logger = get_logger(__name__)

kronos_blp = Blueprint('kronos', __name__)

_kline_service = KlineService()


@kronos_blp.route('/models', methods=['GET'])
@login_required
def kronos_models():
    """Get list of available Kronos models."""
    models = KronosService.get_available_models()
    return jsonify({
        'code': 0,
        'data': {
            'models': models,
            'current_model': _current_model_name,
        }
    })


@kronos_blp.route('/load-model', methods=['POST'])
@login_required
def kronos_load_model():
    """Load a specific Kronos model by name."""
    try:
        data = request.get_json(silent=True) or {}
        model_name = (data.get('model') or '').strip()

        if not model_name:
            return jsonify({'code': 1, 'message': 'model name is required'}), 400

        logger.info(f'Loading Kronos model: {model_name}')
        KronosService.load_model(model_name)

        return jsonify({
            'code': 0,
            'message': f'Model {model_name} loaded successfully',
            'data': {
                'model_name': _current_model_name,
                'model_config': _KRONOS_CONFIG,
            }
        })

    except ValueError as exc:
        return jsonify({'code': 1, 'message': str(exc)}), 400
    except Exception as exc:
        logger.error(f'Failed to load model: {exc}', exc_info=True)
        return jsonify({'code': 1, 'message': f'Failed to load model: {str(exc)}'}), 500


@kronos_blp.route('/predict', methods=['GET'])
@login_required
def kronos_predict():
    """Generate stock price predictions using Kronos foundation model.

    Query params:
        market, symbol     (required)
        timeframe          (default 1D)
        lookback           60..512 (default 400)
        pred_len           1..240 (default 120)
        T                  0.1..2.0 (default 1.0)
        top_p              0.1..1.0 (default 0.9)
        apply_price_limit  true/false (default true)
    """
    market = (request.args.get('market') or '').strip()
    symbol = (request.args.get('symbol') or '').strip()
    timeframe = (request.args.get('timeframe') or '1D').strip()

    try:
        lookback = int(request.args.get('lookback') or 400)
        lookback = max(60, min(512, lookback))
    except ValueError:
        lookback = 400

    try:
        pred_len = int(request.args.get('pred_len') or 120)
        pred_len = max(1, min(240, pred_len))
    except ValueError:
        pred_len = 120

    T_raw = request.args.get('T') or request.args.get('temperature')
    try:
        T = float(T_raw) if T_raw else 1.0
        T = max(0.1, min(2.0, T))
    except ValueError:
        T = 1.0

    top_p_raw = request.args.get('top_p') or request.args.get('nucleus_prob')
    try:
        top_p = float(top_p_raw) if top_p_raw else 0.9
        top_p = max(0.1, min(1.0, top_p))
    except ValueError:
        top_p = 0.9

    apply_price_limit = request.args.get('apply_price_limit', 'true').lower() == 'true'

    if not market or not symbol:
        return jsonify({'code': 1, 'message': 'market and symbol are required'}), 400

    try:
        logger.info(f'Kronos prediction request: {market}/{symbol} timeframe={timeframe}')

        rows = _kline_service.get_kline(
            market=market,
            symbol=symbol,
            timeframe=timeframe,
            limit=lookback + pred_len,
        ) or []

        if len(rows) < lookback:
            return jsonify({'code': 1, 'message': f'Insufficient data: need {lookback} rows, got {len(rows)}'}), 400

        df = pd.DataFrame(rows)

        if 'datetime' in df.columns:
            df['date'] = pd.to_datetime(df['datetime'])
        elif 'timestamps' in df.columns:
            df['date'] = pd.to_datetime(df['timestamps'])

        col_mapping = {'c': 'close', 'o': 'open', 'h': 'high', 'l': 'low', 'v': 'volume'}
        df = df.rename(columns={k: v for k, v in col_mapping.items() if k in df.columns})

        required = ['open', 'high', 'low', 'close']
        missing = [c for c in required if c not in df.columns]
        if missing:
            return jsonify({'code': 1, 'message': f'Kline data missing columns: {missing}'}), 500

        kronos = KronosService()
        pred_df = kronos.predict(
            df=df,
            pred_len=pred_len,
            lookback=lookback,
            T=T,
            top_p=top_p,
        )

        if apply_price_limit and market == 'CNStock':
            last_close = df['close'].iloc[-1]
            pred_df = kronos.apply_price_limits(pred_df, last_close)

        actual_df = df.tail(lookback).copy()
        actual_df['type'] = 'actual'
        pred_df['type'] = 'prediction'

        combined = pd.concat([actual_df, pred_df], ignore_index=True)

        predictions = []
        for _, row in combined.iterrows():
            predictions.append({
                'date': row['date'].isoformat() if hasattr(row['date'], 'isoformat') else str(row['date']),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close']),
                'volume': float(row['volume']) if 'volume' in row else 0,
                'type': row.get('type', 'actual'),
            })

        current_price = float(df['close'].iloc[-1])
        max_pred_price = float(pred_df['high'].max())
        min_pred_price = float(pred_df['low'].min())
        last_pred_price = float(pred_df['close'].iloc[-1])
        up_or_down = 'up' if last_pred_price >= current_price else 'down'

        return jsonify({
            'code': 0,
            'data': {
                'market': market,
                'symbol': symbol,
                'timeframe': timeframe,
                'lookback': lookback,
                'pred_len': pred_len,
                'current_price': current_price,
                'max_pred_price': max_pred_price,
                'min_pred_price': min_pred_price,
                'last_pred_price': last_pred_price,
                'up_or_down': up_or_down,
                'actual_points': len(actual_df),
                'predicted_points': len(pred_df),
                'predict_time': pd.Timestamp.now().isoformat(),
                'predictions': predictions,
            }
        })

    except Exception as exc:
        logger.error(f'Kronos prediction failed: {exc}', exc_info=True)
        return jsonify({'code': 1, 'message': f'Kronos prediction failed: {str(exc)}'}), 500


@kronos_blp.route('/health', methods=['GET'])
@login_required
def kronos_health():
    """Check if Kronos model is available."""
    try:
        from app.services.kronos_service import _KRONOS_LOADED, _KRONOS_CONFIG
        return jsonify({
            'code': 0,
            'data': {
                'status': 'loaded' if _KRONOS_LOADED else 'not_loaded',
                'available': _KRONOS_LOADED,
                'model_name': _KRONOS_CONFIG.get('model', ''),
                'device': _KRONOS_CONFIG.get('device', ''),
                'max_context': _KRONOS_CONFIG.get('max_context', 512),
            }
        })
    except Exception as exc:
        logger.error(f'Kronos health check failed: {exc}')
        return jsonify({
            'code': 0,
            'data': {
                'status': 'error',
                'available': False,
                'message': str(exc),
            }
        })
