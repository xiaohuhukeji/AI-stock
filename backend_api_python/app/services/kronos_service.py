"""Kronos Financial Foundation Model Service.

This service integrates the Kronos model for stock price prediction.
Kronos is a decoder-only foundation model pre-trained on financial candlestick data.
"""
from __future__ import annotations

import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd

from app.utils.logger import get_logger

logger = get_logger(__name__)

_KRONOS_LOADED = False
_tokenizer = None
_model = None
_predictor = None
_current_model_name = None
_KRONOS_CONFIG = {
    'model': '',
    'tokenizer': '',
    'device': '',
    'max_context': 512,
}

AVAILABLE_MODELS = [
    {
        'name': 'Kronos-mini',
        'model_id': 'NeoQuasar/Kronos-mini',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-2k',
        'max_context': 2048,
        'params': '410万',
        'description': '轻量模型，适合快速推理',
    },
    {
        'name': 'Kronos-small',
        'model_id': 'NeoQuasar/Kronos-small',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'max_context': 512,
        'params': '2470万',
        'description': '小型模型，平衡速度与精度',
    },
    {
        'name': 'Kronos-base',
        'model_id': 'NeoQuasar/Kronos-base',
        'tokenizer_id': 'NeoQuasar/Kronos-Tokenizer-base',
        'max_context': 512,
        'params': '1.023亿',
        'description': '基础模型，预测精度更高',
    },
]


def _ensure_kronos_path():
    kronos_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "Kronos")
    kronos_path = os.path.abspath(kronos_path)
    if kronos_path not in sys.path:
        sys.path.insert(0, kronos_path)
    return kronos_path


def _load_kronos_model(model_id=None, tokenizer_id=None, max_context=None):
    global _KRONOS_LOADED, _tokenizer, _model, _predictor, _current_model_name

    device = os.getenv("KRONOS_DEVICE", "cpu")
    default_model = os.getenv("KRONOS_MODEL", "NeoQuasar/Kronos-small")
    default_tokenizer = os.getenv("KRONOS_TOKENIZER", "NeoQuasar/Kronos-Tokenizer-base")
    default_max_context = int(os.getenv("KRONOS_MAX_CONTEXT", "512"))

    model_id = model_id or default_model
    tokenizer_id = tokenizer_id or default_tokenizer
    max_context = max_context or default_max_context

    if _KRONOS_LOADED and _current_model_name == model_id:
        return

    try:
        kronos_path = _ensure_kronos_path()
        logger.info(f"Loading Kronos model: {model_id}")

        start_time = time.time()
        from model import Kronos, KronosTokenizer, KronosPredictor

        _KRONOS_CONFIG['model'] = model_id
        _KRONOS_CONFIG['tokenizer'] = tokenizer_id
        _KRONOS_CONFIG['device'] = device
        _KRONOS_CONFIG['max_context'] = max_context

        logger.info(f"Loading tokenizer: {tokenizer_id}")
        _tokenizer = KronosTokenizer.from_pretrained(tokenizer_id)

        logger.info(f"Loading model: {model_id}")
        _model = Kronos.from_pretrained(model_id)

        logger.info(f"Initializing predictor with device={device}, max_context={max_context}")
        _predictor = KronosPredictor(_model, _tokenizer, device=device, max_context=max_context)

        _current_model_name = model_id
        _KRONOS_LOADED = True
        load_time = time.time() - start_time
        logger.info(f"Kronos model loaded successfully in {load_time:.2f}s")

    except Exception as exc:
        logger.error(f"Failed to load Kronos model: {exc}", exc_info=True)
        raise


class KronosService:
    """Service for stock price prediction using Kronos foundation model."""

    def __init__(self, model_name=None):
        if model_name:
            self.load_model(model_name)
        else:
            _load_kronos_model()

    @staticmethod
    def get_available_models():
        return AVAILABLE_MODELS

    @staticmethod
    def load_model(model_name: str):
        model_info = None
        for m in AVAILABLE_MODELS:
            if m['name'] == model_name or m['model_id'] == model_name:
                model_info = m
                break
        if not model_info:
            raise ValueError(f"Unknown model: {model_name}. Available: {[m['name'] for m in AVAILABLE_MODELS]}")
        _load_kronos_model(
            model_id=model_info['model_id'],
            tokenizer_id=model_info['tokenizer_id'],
            max_context=model_info['max_context'],
        )

    def predict(
        self,
        df: pd.DataFrame,
        pred_len: int = 120,
        lookback: int = 400,
        T: float = 1.0,
        top_p: float = 0.9,
        sample_count: int = 1,
    ) -> pd.DataFrame:
        """
        Generate price predictions using Kronos model.

        Args:
            df: DataFrame containing historical OHLCV data
            pred_len: Number of periods to predict
            lookback: Number of historical periods to use as context
            T: Temperature for sampling
            top_p: Nucleus sampling probability
            sample_count: Number of forecast paths to generate and average

        Returns:
            DataFrame with predicted OHLCV data
        """
        if not _KRONOS_LOADED:
            _load_kronos_model()

        required_cols = ["open", "high", "low", "close"]
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        lookback = min(lookback, len(df))
        if lookback < 60:
            raise ValueError(f"Insufficient data: need at least 60 rows, got {len(df)}")

        pred_len = min(pred_len, 240)

        x_df = df.iloc[-lookback:][["open", "high", "low", "close"]]

        if "volume" in df.columns:
            x_df["volume"] = df.iloc[-lookback:]["volume"].values
        else:
            x_df["volume"] = 0

        if "amount" in df.columns:
            x_df["amount"] = df.iloc[-lookback:]["amount"].values
        else:
            x_df["amount"] = 0

        timestamp_col = "timestamps" if "timestamps" in df.columns else "date"
        if timestamp_col in df.columns:
            x_timestamp = df.iloc[-lookback:][timestamp_col]
            last_date = pd.to_datetime(x_timestamp.iloc[-1])
        else:
            x_timestamp = pd.Series(pd.date_range(end=datetime.now(), periods=lookback, freq="B"))
            last_date = x_timestamp.iloc[-1]

        future_dates = self._generate_future_dates(last_date, pred_len)
        y_timestamp = pd.Series(future_dates)

        logger.info(f"Generating prediction: lookback={lookback}, pred_len={pred_len}")
        start_time = time.time()

        pred_df = _predictor.predict(
            df=x_df,
            x_timestamp=x_timestamp,
            y_timestamp=y_timestamp,
            pred_len=pred_len,
            T=T,
            top_p=top_p,
            sample_count=sample_count,
        )

        pred_df["date"] = y_timestamp.values
        pred_time = time.time() - start_time
        logger.info(f"Prediction completed in {pred_time:.2f}s")

        return pred_df

    def predict_batch(
        self,
        df_list: List[pd.DataFrame],
        pred_len: int = 120,
        lookback: int = 400,
        T: float = 1.0,
        top_p: float = 0.9,
        sample_count: int = 1,
    ) -> List[pd.DataFrame]:
        """
        Generate batch predictions for multiple stocks.

        Args:
            df_list: List of DataFrames containing historical OHLCV data
            pred_len: Number of periods to predict
            lookback: Number of historical periods to use as context
            T: Temperature for sampling
            top_p: Nucleus sampling probability
            sample_count: Number of forecast paths to generate and average

        Returns:
            List of DataFrames with predicted OHLCV data
        """
        if not _KRONOS_LOADED:
            _load_kronos_model()

        results = []
        for df in df_list:
            try:
                pred_df = self.predict(df, pred_len, lookback, T, top_p, sample_count)
                results.append(pred_df)
            except Exception as exc:
                logger.error(f"Batch prediction failed for one dataset: {exc}")
                results.append(pd.DataFrame())

        return results

    @staticmethod
    def _generate_future_dates(last_date: datetime, count: int) -> List[datetime]:
        """Generate future trading dates excluding weekends and major holidays."""
        dates = []
        current = last_date + timedelta(days=1)

        holidays_2025_2026 = [
            datetime(2025, 1, 1), datetime(2025, 1, 2), datetime(2025, 1, 3),
            datetime(2025, 4, 4), datetime(2025, 4, 5), datetime(2025, 4, 6),
            datetime(2025, 5, 1), datetime(2025, 5, 2), datetime(2025, 5, 3),
            datetime(2025, 5, 4), datetime(2025, 5, 5),
            datetime(2025, 6, 7), datetime(2025, 6, 8), datetime(2025, 6, 9),
            datetime(2025, 9, 29), datetime(2025, 9, 30),
            datetime(2025, 10, 1), datetime(2025, 10, 2), datetime(2025, 10, 3),
            datetime(2025, 10, 4), datetime(2025, 10, 5), datetime(2025, 10, 6),
            datetime(2025, 10, 7), datetime(2025, 10, 8),
            datetime(2026, 1, 1), datetime(2026, 1, 2), datetime(2026, 1, 3),
            datetime(2026, 4, 3), datetime(2026, 4, 4), datetime(2026, 4, 5),
            datetime(2026, 5, 1), datetime(2026, 5, 2), datetime(2026, 5, 3),
            datetime(2026, 5, 4), datetime(2026, 5, 5),
            datetime(2026, 6, 8), datetime(2026, 6, 9), datetime(2026, 6, 10),
            datetime(2026, 9, 28), datetime(2026, 9, 29),
            datetime(2026, 10, 1), datetime(2026, 10, 2), datetime(2026, 10, 3),
            datetime(2026, 10, 4), datetime(2026, 10, 5), datetime(2026, 10, 6),
            datetime(2026, 10, 7), datetime(2026, 10, 8),
        ]

        while len(dates) < count:
            if current.weekday() < 5 and current not in holidays_2025_2026:
                dates.append(current)
            current += timedelta(days=1)

        return dates

    @staticmethod
    def apply_price_limits(pred_df: pd.DataFrame, last_close: float, limit_rate: float = 0.1) -> pd.DataFrame:
        """Apply price limits to predictions (±10% for A-shares)."""
        pred_df = pred_df.copy().reset_index(drop=True)
        cols = ["open", "high", "low", "close"]
        pred_df[cols] = pred_df[cols].astype("float64")

        for i in range(len(pred_df)):
            limit_up = last_close * (1 + limit_rate)
            limit_down = last_close * (1 - limit_rate)

            for col in cols:
                value = pred_df.at[i, col]
                if pd.notna(value):
                    pred_df.at[i, col] = float(max(min(value, limit_up), limit_down))

            last_close = float(pred_df.at[i, "close"])

        return pred_df

    def get_prediction_summary(self, df: pd.DataFrame, pred_df: pd.DataFrame) -> Dict:
        """Generate a summary of prediction results."""
        last_close = df["close"].iloc[-1]
        first_pred_close = pred_df["close"].iloc[0]
        last_pred_close = pred_df["close"].iloc[-1]

        summary = {
            "current_price": float(last_close),
            "first_predicted_price": float(first_pred_close),
            "last_predicted_price": float(last_pred_close),
            "price_change": float(last_pred_close - last_close),
            "price_change_pct": float((last_pred_close / last_close - 1) * 100),
            "predicted_high": float(pred_df["high"].max()),
            "predicted_low": float(pred_df["low"].min()),
            "predicted_avg": float(pred_df["close"].mean()),
            "predicted_std": float(pred_df["close"].std()),
            "prediction_days": len(pred_df),
            "start_date": pred_df["date"].iloc[0].isoformat() if "date" in pred_df.columns else None,
            "end_date": pred_df["date"].iloc[-1].isoformat() if "date" in pred_df.columns else None,
        }

        return summary