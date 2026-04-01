from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf


class StockDataService:
    def __init__(self, alpha_vantage_api_key: str = "") -> None:
        self.alpha_vantage_api_key = alpha_vantage_api_key.strip()

    @st.cache_data(show_spinner=False, ttl=900)
    def _cached_yahoo_download(
        _self,
        symbol: str,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        frame = yf.download(symbol, period=period, start=start, end=end, progress=False, auto_adjust=False)
        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)
        return frame

    @st.cache_data(show_spinner=False, ttl=900)
    def _cached_alpha_vantage_download(_self, symbol: str, api_key: str) -> pd.DataFrame:
        params = {
            "function": "TIME_SERIES_DAILY_ADJUSTED",
            "symbol": symbol,
            "outputsize": "full",
            "apikey": api_key,
        }
        url = f"https://www.alphavantage.co/query?{urlencode(params)}"
        with urlopen(url, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        if "Error Message" in payload:
            raise ValueError(payload["Error Message"])
        if "Note" in payload:
            raise ValueError(payload["Note"])

        series = payload.get("Time Series (Daily)", {})
        if not series:
            return pd.DataFrame()

        rows: list[dict[str, float | str]] = []
        for raw_date, values in series.items():
            rows.append(
                {
                    "Date": raw_date,
                    "Open": float(values["1. open"]),
                    "High": float(values["2. high"]),
                    "Low": float(values["3. low"]),
                    "Close": float(values["4. close"]),
                    "Adj Close": float(values["5. adjusted close"]),
                    "Volume": float(values["6. volume"]),
                }
            )

        frame = pd.DataFrame(rows)
        frame["Date"] = pd.to_datetime(frame["Date"])
        return frame.sort_values("Date").reset_index(drop=True)

    def download_stock_data(
        self,
        symbol: str,
        period: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> pd.DataFrame:
        frame = pd.DataFrame()
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                frame = self._cached_yahoo_download(symbol=symbol, period=period, start=start, end=end)
                if not frame.empty:
                    return frame.reset_index()
            except Exception as error:
                last_error = error
            time.sleep(1.5 * (attempt + 1))

        if self.alpha_vantage_api_key:
            fallback = self._download_from_alpha_vantage(symbol)
            if not fallback.empty:
                if start:
                    fallback = fallback[fallback["Date"] >= pd.to_datetime(start)]
                if end:
                    fallback = fallback[fallback["Date"] <= pd.to_datetime(end)]
                return fallback.reset_index(drop=True)

        if last_error:
            raise ValueError(
                "Stock data could not be fetched right now. Yahoo Finance may be rate-limiting requests. "
                "Add ALPHA_VANTAGE_API_KEY in .env to enable fallback data."
            ) from last_error
        raise ValueError(
            "No historical data returned. Verify the stock ticker and try again. "
            "If Yahoo Finance keeps rate-limiting, add ALPHA_VANTAGE_API_KEY in .env."
        )

    def build_feature_frame(self, history: pd.DataFrame) -> pd.DataFrame:
        frame = history.copy()
        frame["Return"] = frame["Close"].pct_change()
        frame["SMA_10"] = frame["Close"].rolling(window=10).mean()
        frame["SMA_20"] = frame["Close"].rolling(window=20).mean()
        frame["EMA_10"] = frame["Close"].ewm(span=10, adjust=False).mean()
        frame["EMA_20"] = frame["Close"].ewm(span=20, adjust=False).mean()
        frame["Momentum_5"] = frame["Close"] - frame["Close"].shift(5)
        frame["Volatility"] = frame["Return"].rolling(window=10).std()
        frame["RSI"] = self._relative_strength_index(frame["Close"])
        frame["MACD"] = self._macd(frame["Close"])
        frame["Signal_Line"] = frame["MACD"].ewm(span=9, adjust=False).mean()
        frame["Volume_Trend"] = frame["Volume"].pct_change().rolling(window=5).mean()
        frame["Target"] = (frame["Close"].shift(-1) > frame["Close"]).astype(int)
        frame = frame.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)
        if len(frame) < 60:
            raise ValueError("Not enough clean data points were generated for model training.")
        return frame

    def current_market_snapshot(self, frame: pd.DataFrame) -> dict[str, float]:
        latest = frame.iloc[-1]
        previous_close = frame["Close"].iloc[-2] if len(frame) > 1 else latest["Close"]
        daily_change = ((latest["Close"] / previous_close) - 1) * 100 if previous_close else 0.0
        return {
            "open": float(latest["Open"]),
            "high": float(latest["High"]),
            "low": float(latest["Low"]),
            "close": float(latest["Close"]),
            "volume": float(latest["Volume"]),
            "daily_change_pct": float(daily_change),
        }

    def _download_from_alpha_vantage(self, symbol: str) -> pd.DataFrame:
        try:
            return self._cached_alpha_vantage_download(symbol=symbol, api_key=self.alpha_vantage_api_key)
        except (ValueError, HTTPError, URLError):
            return pd.DataFrame()

    @staticmethod
    def _relative_strength_index(series: pd.Series, window: int = 14) -> pd.Series:
        delta = series.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        average_gain = gain.rolling(window=window).mean()
        average_loss = loss.rolling(window=window).mean()
        relative_strength = average_gain / average_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + relative_strength))
        return rsi.fillna(50)

    @staticmethod
    def _macd(series: pd.Series) -> pd.Series:
        short_ema = series.ewm(span=12, adjust=False).mean()
        long_ema = series.ewm(span=26, adjust=False).mean()
        return short_ema - long_ema
