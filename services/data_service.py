from __future__ import annotations

import os
import time
import json
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import pandas as pd
import streamlit as st

for proxy_key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    if os.environ.get(proxy_key) == "http://127.0.0.1:9":
        os.environ.pop(proxy_key, None)


class StockDataService:
    def __init__(self, alpha_vantage_api_key: str) -> None:
        self.alpha_vantage_api_key = alpha_vantage_api_key.strip()

    @st.cache_data(show_spinner=False, ttl=900)
    def _cached_alpha_vantage_download(
        _self,
        symbol: str,
        api_key: str,
    ) -> pd.DataFrame:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "outputsize": "compact",
            "apikey": api_key,
        }
        url = f"https://www.alphavantage.co/query?{urlencode(params)}"
        with urlopen(url, timeout=20) as response:
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
                    "Adj Close": float(values["4. close"]),
                    "Volume": float(values["5. volume"]),
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
        if not self.alpha_vantage_api_key:
            raise ValueError("ALPHA_VANTAGE_API_KEY is missing. Add it in your .env file.")

        last_error: Exception | None = None

        for attempt in range(3):
            try:
                frame = self._cached_alpha_vantage_download(symbol=symbol, api_key=self.alpha_vantage_api_key)
                if not frame.empty:
                    if start:
                        frame = frame[frame["Date"] >= pd.to_datetime(start)]
                    if end:
                        frame = frame[frame["Date"] <= pd.to_datetime(end)]
                    if not frame.empty:
                        return frame.reset_index(drop=True)
            except Exception as error:
                last_error = error
            time.sleep(12 if attempt == 0 else 18)

        if last_error:
            raise ValueError(
                "Stock data could not be fetched from Alpha Vantage right now. "
                "Verify the ticker, API key, or wait a moment if the API limit was reached."
            ) from last_error
        raise ValueError(
            "No historical data returned from Alpha Vantage. Verify the stock ticker and try again."
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
