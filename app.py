from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from services.config import AppConfig
from services.data_service import StockDataService
from services.db_service import MongoService
from services.model_service import HybridTrendPredictor


st.set_page_config(page_title="MarketPulse AI", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

PAGES = ["Landing", "Prediction Dashboard", "Stock Comparison", "Model Insights", "History / Logs", "About Project"]
TICKER_OPTIONS = [
    "AAPL",
    "MSFT",
    "NVDA",
    "AMZN",
    "GOOGL",
    "META",
    "TSLA",
    "NFLX",
    "AMD",
    "INTC",
    "JPM",
    "BAC",
    "V",
    "MA",
    "WMT",
    "KO",
    "PEP",
    "XOM",
    "CVX",
    "DIS",
    "NKE",
    "PFE",
    "JNJ",
    "ABBV",
    "CRM",
    "ORCL",
    "ADBE",
    "CSCO",
    "QCOM",
    "SHOP",
    "UBER",
    "PYPL",
    "SBIN.NS",
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "LT.NS",
    "ITC.NS",
    "BHARTIARTL.NS",
    "KOTAKBANK.NS",
    "AXISBANK.NS",
    "ASIANPAINT.NS",
    "MARUTI.NS",
    "HINDUNILVR.NS",
    "BAJFINANCE.NS",
    "WIPRO.NS",
    "TITAN.NS",
    "SUNPHARMA.NS",
    "ULTRACEMCO.NS",
    "NTPC.NS",
    "POWERGRID.NS",
    "TATAMOTORS.NS",
    "TATASTEEL.NS",
    "ADANIENT.NS",
    "ADANIPORTS.NS",
    "ONGC.NS",
    "COALINDIA.NS",
    "HCLTECH.NS",
    "TECHM.NS",
    "Custom",
]


def load_styles() -> None:
    st.markdown(f"<style>{Path('styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


@st.cache_resource(show_spinner=False)
def get_services() -> tuple[StockDataService, MongoService]:
    config = AppConfig()
    return StockDataService(config.alpha_vantage_api_key), MongoService(config.mongo_uri, config.database_name)


def initialize_state() -> None:
    st.session_state.setdefault("active_page", "Landing")
    st.session_state.setdefault("analysis_result", None)
    st.session_state.setdefault("comparison_result", None)


def status_meta(probability: float) -> dict[str, str]:
    if probability >= 0.6:
        return {"label": "Bullish", "class": "bullish", "note": "Momentum and trend signals are tilted upward."}
    if probability <= 0.4:
        return {"label": "Bearish", "class": "bearish", "note": "Signals indicate downside pressure and weaker structure."}
    return {"label": "Neutral", "class": "neutral", "note": "Indicator mix is balanced and conviction is moderate."}


def format_percent(value: float) -> str:
    return f"{value * 100:.2f}%"


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def comparison_score(metrics: dict[str, Any], snapshot: dict[str, float]) -> float:
    signal_strength = metrics["probability"]
    model_quality = (metrics["accuracy"] + metrics["precision"] + metrics["recall"] + metrics["f1_score"]) / 4
    recent_momentum = clamp(snapshot["daily_change_pct"] / 5, -1.0, 1.0)
    score = (signal_strength * 0.7) + (model_quality * 0.25) + (max(recent_momentum, 0.0) * 0.05)
    return float(score)


def get_date_bounds(selected_range: tuple[date, date] | list[date] | date) -> tuple[date, date]:
    if isinstance(selected_range, tuple):
        return selected_range
    if isinstance(selected_range, list) and len(selected_range) == 2:
        return selected_range[0], selected_range[1]
    if isinstance(selected_range, date):
        return selected_range - timedelta(days=365), selected_range
    return date.today() - timedelta(days=365), date.today()


def prepare_uploaded_history(uploaded_file: Any) -> pd.DataFrame:
    frame = pd.read_csv(uploaded_file)
    renamed_columns = {column: column.strip() for column in frame.columns}
    frame = frame.rename(columns=renamed_columns)
    required_columns = ["Date", "Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required_columns if column not in frame.columns]
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {', '.join(missing)}. "
            "Use a Yahoo Finance style historical-data CSV."
        )

    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    numeric_columns = ["Open", "High", "Low", "Close", "Volume"]
    if "Adj Close" not in frame.columns:
        frame["Adj Close"] = frame["Close"]
    else:
        numeric_columns.append("Adj Close")

    for column in numeric_columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    frame = frame.dropna(subset=["Date", "Open", "High", "Low", "Close", "Volume"]).sort_values("Date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("Uploaded CSV does not contain usable historical rows after cleaning.")
    return frame


def section_heading(eyebrow: str, title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <p>{eyebrow}</p>
            <h3>{title}</h3>
            <span>{copy}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def stat_card(title: str, value: str, subtitle: str, tone: str = "default") -> None:
    st.markdown(
        f"""
        <div class="stat-card {tone}">
            <p>{title}</p>
            <h4>{value}</h4>
            <span>{subtitle}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def highlight_card(title: str, body: str, accent: str) -> None:
    st.markdown(
        f"""
        <div class="highlight-card {accent}">
            <h4>{title}</h4>
            <p>{body}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def status_chip(label: str, tone_class: str) -> str:
    return f'<span class="status-chip {tone_class}">{label}</span>'


def build_candlestick_figure(frame: pd.DataFrame, symbol: str) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(
        go.Candlestick(
            x=frame["Date"],
            open=frame["Open"],
            high=frame["High"],
            low=frame["Low"],
            close=frame["Close"],
            name="Price",
            increasing_line_color="#17a673",
            decreasing_line_color="#df4f4f",
        )
    )
    figure.add_trace(go.Scatter(x=frame["Date"], y=frame["SMA_10"], mode="lines", name="SMA 10", line=dict(color="#2962ff", width=2)))
    figure.add_trace(go.Scatter(x=frame["Date"], y=frame["EMA_20"], mode="lines", name="EMA 20", line=dict(color="#fb8c00", width=2)))
    figure.update_layout(
        title=f"{symbol} Price Action",
        height=540,
        margin=dict(l=16, r=16, t=54, b=12),
        xaxis_rangeslider_visible=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right"),
    )
    figure.update_yaxes(title="Price")
    return figure


def build_rsi_figure(frame: pd.DataFrame) -> go.Figure:
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=frame["Date"], y=frame["RSI"], mode="lines", line=dict(color="#5c6ac4", width=2.5), name="RSI"))
    figure.add_hline(y=70, line_dash="dot", line_color="#df4f4f")
    figure.add_hline(y=30, line_dash="dot", line_color="#17a673")
    figure.update_layout(title="Relative Strength Index", height=260, margin=dict(l=16, r=16, t=48, b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", showlegend=False)
    figure.update_yaxes(range=[0, 100])
    return figure


def build_macd_figure(frame: pd.DataFrame) -> go.Figure:
    histogram = frame["MACD"] - frame["Signal_Line"]
    colors = ["#17a673" if value >= 0 else "#df4f4f" for value in histogram]
    figure = go.Figure()
    figure.add_trace(go.Bar(x=frame["Date"], y=histogram, name="Histogram", marker_color=colors))
    figure.add_trace(go.Scatter(x=frame["Date"], y=frame["MACD"], mode="lines", name="MACD", line=dict(color="#111827", width=2)))
    figure.add_trace(go.Scatter(x=frame["Date"], y=frame["Signal_Line"], mode="lines", name="Signal", line=dict(color="#fb8c00", width=2)))
    figure.update_layout(title="MACD Momentum", height=280, margin=dict(l=16, r=16, t=48, b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
    return figure


def build_confusion_matrix_figure(matrix: list[list[int]]) -> go.Figure:
    figure = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=["Pred Down", "Pred Up"],
            y=["Actual Down", "Actual Up"],
            colorscale=[[0, "#eef2f7"], [0.5, "#9db4ff"], [1, "#204ecf"]],
            text=matrix,
            texttemplate="%{text}",
            showscale=False,
        )
    )
    figure.update_layout(title="Confusion Matrix", height=310, margin=dict(l=16, r=16, t=48, b=12), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    return figure


def build_probability_gauge(probability: float) -> go.Figure:
    figure = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=probability * 100,
            number={"suffix": "%"},
            title={"text": "Uptrend Probability"},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": "#204ecf"},
                "steps": [{"range": [0, 40], "color": "#f4d7d7"}, {"range": [40, 60], "color": "#f1efe9"}, {"range": [60, 100], "color": "#d9f0e8"}],
            },
        )
    )
    figure.update_layout(height=310, margin=dict(l=16, r=16, t=48, b=12), paper_bgcolor="rgba(0,0,0,0)")
    return figure


def render_shell_header() -> None:
    st.markdown(
        """
        <div class="shell-header">
            <div>
                <div class="brand-mark">MP</div>
                <div>
                    <p class="brand-kicker">Hybrid ANN + Genetic Search</p>
                    <h2>MarketPulse AI</h2>
                </div>
            </div>
            <div class="header-meta">
                <span class="mini-chip">Chart-first Interface</span>
                <span class="mini-chip">MongoDB Atlas Ready</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_top_navigation() -> None:
    selected = st.radio("Navigation", PAGES, index=PAGES.index(st.session_state.active_page), horizontal=True, label_visibility="collapsed")
    st.session_state.active_page = selected


def render_sidebar() -> dict[str, Any]:
    _, mongo_service = get_services()
    mongo_error = getattr(mongo_service, "error_message", "")
    with st.sidebar:
        st.markdown("### Trading Controls")
        default_range = (date.today() - timedelta(days=365), date.today())
        selected_ticker = ""
        custom_symbol = ""
        uploaded_csv = None
        comparison_symbols: list[str] = []
        predict_clicked = False
        compare_clicked = False
        if st.session_state.active_page == "Stock Comparison":
            comparison_symbols = st.multiselect(
                "Compare tickers",
                options=[ticker for ticker in TICKER_OPTIONS if ticker != "Custom"],
                default=["AAPL", "MSFT", "NVDA"],
                max_selections=5,
                help="Select two or more stocks to rank by model-based buy strength.",
            )
            date_range = st.date_input("Comparison range", value=default_range, help="Historical window used to compare all selected stocks.")
        else:
            selected_ticker = st.selectbox(
                "Ticker list",
                options=TICKER_OPTIONS,
                index=0,
                help="Search and select a popular ticker, or choose Custom to type any Yahoo Finance symbol.",
            )
            if selected_ticker == "Custom":
                custom_symbol = st.text_input(
                    "Custom ticker",
                    value="",
                    help="Enter any Yahoo Finance ticker, for example AAPL or RELIANCE.NS.",
                )
            uploaded_csv = st.file_uploader(
                "Offline CSV data",
                type=["csv"],
                help="Optional. Upload historical stock data CSV to run the app without internet APIs.",
            )
            date_range = st.date_input("Date range", value=default_range, help="Window used to train the ANN-GA model.")
        ga_population = st.slider("GA population", 12, 80, 28, 2, help="More candidates increase search breadth.")
        ga_generations = st.slider("GA generations", 6, 40, 14, 1, help="More generations increase search depth.")
        if st.session_state.active_page == "Stock Comparison":
            compare_clicked = st.button("Compare Stocks", use_container_width=True, type="primary")
        else:
            predict_clicked = st.button("Run Prediction", use_container_width=True, type="primary")
        st.markdown("---")
        mongo_status = "Connected" if mongo_service.available else "Offline"
        st.markdown(
            f"""
            <div class="sidebar-card">
                <div class="sidebar-row"><span>Database</span><strong>{mongo_status}</strong></div>
                <div class="sidebar-row"><span>Model</span><strong>ANN + GA</strong></div>
                <div class="sidebar-row"><span>Feed</span><strong>Yahoo Finance</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if not mongo_service.available and mongo_error:
            st.caption(f"MongoDB error: {mongo_error}")
    symbol = custom_symbol if selected_ticker == "Custom" else selected_ticker
    return {
        "symbol": symbol.upper().strip(),
        "uploaded_csv": uploaded_csv,
        "comparison_symbols": comparison_symbols,
        "date_range": date_range,
        "population": ga_population,
        "generations": ga_generations,
        "predict_clicked": predict_clicked,
        "compare_clicked": compare_clicked,
    }


def analyze_symbol(
    symbol: str,
    start_date: date,
    end_date: date,
    population: int,
    generations: int,
    stock_service: StockDataService,
) -> dict[str, Any]:
    history = stock_service.download_stock_data(
        symbol=symbol,
        start=start_date.isoformat(),
        end=(end_date + timedelta(days=1)).isoformat(),
    )
    features = stock_service.build_feature_frame(history)
    predictor = HybridTrendPredictor(population_size=population, generations=generations, random_state=42)
    metrics = predictor.fit_predict(features)
    snapshot = stock_service.current_market_snapshot(history)
    signal = status_meta(metrics["probability"])
    score = comparison_score(metrics, snapshot)
    return {
        "symbol": symbol,
        "history": history,
        "features": features,
        "metrics": metrics,
        "snapshot": snapshot,
        "signal": signal,
        "score": score,
        "feature_snapshot": predictor.latest_feature_snapshot(features),
    }


def run_prediction(controls: dict[str, Any]) -> None:
    symbol = controls["symbol"]
    uploaded_csv = controls.get("uploaded_csv")
    if not symbol and uploaded_csv is None:
        st.error("Please enter a stock ticker before running the model.")
        return

    start_date, end_date = get_date_bounds(controls["date_range"])
    if end_date <= start_date:
        st.error("The end date must be later than the start date.")
        return

    stock_service, mongo_service = get_services()
    try:
        with st.spinner("Preparing indicators, optimizing ANN parameters, and generating the trend outlook..."):
            if uploaded_csv is not None:
                history = prepare_uploaded_history(uploaded_csv)
                if not symbol:
                    symbol = Path(uploaded_csv.name).stem.upper()
                history = history[
                    (history["Date"] >= pd.to_datetime(start_date)) & (history["Date"] <= pd.to_datetime(end_date))
                ].reset_index(drop=True)
                if history.empty:
                    raise ValueError("The uploaded CSV has no rows inside the selected date range.")
                predictor = HybridTrendPredictor(population_size=controls["population"], generations=controls["generations"], random_state=42)
                features = stock_service.build_feature_frame(history)
                metrics = predictor.fit_predict(features)
                snapshot = stock_service.current_market_snapshot(history)
                feature_snapshot = predictor.latest_feature_snapshot(features)
            else:
                analysis = analyze_symbol(
                    symbol=symbol,
                    start_date=start_date,
                    end_date=end_date,
                    population=controls["population"],
                    generations=controls["generations"],
                    stock_service=stock_service,
                )
                history = analysis["history"]
                features = analysis["features"]
                metrics = analysis["metrics"]
                snapshot = analysis["snapshot"]
                feature_snapshot = analysis["feature_snapshot"]
            signal = status_meta(metrics["probability"])
            mongo_service.store_prediction(
                {
                    "symbol": symbol,
                    "date_start": datetime.combine(start_date, time.min),
                    "date_end": datetime.combine(end_date, time.max),
                    "predicted_trend": signal["label"],
                    "bullish_probability": round(metrics["probability"], 4),
                    "validation_accuracy": round(metrics["accuracy"], 4),
                    "precision": round(metrics["precision"], 4),
                    "recall": round(metrics["recall"], 4),
                    "f1_score": round(metrics["f1_score"], 4),
                    "best_genome": metrics["best_genome"],
                    "confusion_matrix": metrics["confusion_matrix"],
                    "created_at": datetime.utcnow(),
                    "market_snapshot": snapshot,
                    "feature_snapshot": feature_snapshot,
                }
            )
    except Exception as error:
        st.error(f"Unable to complete the analysis: {error}")
        return

    st.session_state.analysis_result = {
        "symbol": symbol,
        "history": history,
        "features": features,
        "metrics": metrics,
        "signal": signal,
        "snapshot": snapshot,
        "date_start": start_date,
        "date_end": end_date,
        "generated_at": datetime.now(),
    }
    st.session_state.active_page = "Prediction Dashboard"


def run_comparison(controls: dict[str, Any]) -> None:
    symbols = controls.get("comparison_symbols", [])
    if len(symbols) < 2:
        st.error("Select at least two stocks to compare.")
        return

    start_date, end_date = get_date_bounds(controls["date_range"])
    if end_date <= start_date:
        st.error("The end date must be later than the start date.")
        return

    stock_service, _ = get_services()
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    with st.spinner("Comparing stocks with the ANN-GA engine and ranking the strongest buy setups..."):
        for symbol in symbols:
            try:
                results.append(
                    analyze_symbol(
                        symbol=symbol,
                        start_date=start_date,
                        end_date=end_date,
                        population=controls["population"],
                        generations=controls["generations"],
                        stock_service=stock_service,
                    )
                )
            except Exception as error:
                failures.append(f"{symbol}: {error}")

    if len(results) < 2:
        if failures:
            st.error(
                "Unable to complete the comparison because too few stocks returned usable Yahoo Finance data. "
                f"Failures: {' | '.join(failures)}"
            )
        else:
            st.error("Unable to complete the comparison because too few stocks returned usable data.")
        return

    ranked = sorted(
        results,
        key=lambda item: (item["score"], item["metrics"]["probability"], item["metrics"]["f1_score"]),
        reverse=True,
    )
    st.session_state.comparison_result = {
        "ranked": ranked,
        "failures": failures,
        "date_start": start_date,
        "date_end": end_date,
        "generated_at": datetime.now(),
    }
    st.session_state.active_page = "Stock Comparison"


def render_landing_page() -> None:
    st.markdown(
        """
        <section class="hero-board">
            <div class="hero-copy-wrap">
                <p class="hero-kicker">Professional Stock Trend Intelligence</p>
                <h1>Chart-first forecasting for disciplined investment decision support.</h1>
                <p>MarketPulse AI combines technical indicators, a hybrid ANN-GA model, and MongoDB-backed decision logs in a clean, premium trading-terminal style workspace.</p>
                <div class="hero-actions">
                    <span class="ghost-tag">ANN + GA Engine</span>
                    <span class="ghost-tag">Indicator Stack</span>
                    <span class="ghost-tag">Prediction Logs</span>
                </div>
            </div>
            <div class="hero-stat-grid">
                <div class="hero-stat"><span>Signal Types</span><strong>Bullish / Bearish / Neutral</strong></div>
                <div class="hero-stat"><span>Indicators</span><strong>SMA, EMA, RSI, MACD</strong></div>
                <div class="hero-stat"><span>Storage</span><strong>MongoDB Atlas</strong></div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("Predict Stock", use_container_width=True, type="primary"):
            st.session_state.active_page = "Prediction Dashboard"
            st.rerun()
    with c2:
        if st.button("View Dashboard", use_container_width=True):
            st.session_state.active_page = "Prediction Dashboard"
            st.rerun()
    with c3:
        if st.button("Model Performance", use_container_width=True):
            st.session_state.active_page = "Model Insights"
            st.rerun()

    section_heading("Platform Highlights", "A premium financial workspace with a focused signal path.", "Every section is designed to keep charts dominant, metrics compact, and decision context easy to scan.")
    cols = st.columns(3)
    with cols[0]:
        highlight_card("Terminal-style dashboard", "Large chart panels, compact status cards, and disciplined spacing create a credible trading feel.", "positive")
    with cols[1]:
        highlight_card("Searchable model memory", "Predictions are stored with metrics and time windows so you can audit system behavior over time.", "neutral")
    with cols[2]:
        highlight_card("Confidence-led decision support", "The platform focuses on clarity, probability, and model quality rather than cluttered widgets.", "negative")

    section_heading("Quick Tour", "From market data to logged prediction in one flow.", "Use the sidebar to configure the ticker and date window, then inspect the forecast, technicals, and diagnostics.")
    st.markdown(
        """
        <div class="process-strip">
            <div><span>1</span><strong>Fetch</strong><p>Historical OHLCV data from Yahoo Finance.</p></div>
            <div><span>2</span><strong>Engineer</strong><p>SMA, EMA, RSI, MACD, volatility, momentum.</p></div>
            <div><span>3</span><strong>Optimize</strong><p>Genetic search tunes features and ANN settings.</p></div>
            <div><span>4</span><strong>Log</strong><p>Store output and metrics in MongoDB Atlas.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_prediction_dashboard() -> None:
    result = st.session_state.analysis_result
    section_heading("Prediction Dashboard", "Live stock trend workspace", "Run a forecast from the sidebar, then inspect price structure, momentum, and model conviction.")
    if result is None:
        st.info("No prediction has been generated yet. Use the sidebar controls and click Run Prediction.")
        return

    metrics = result["metrics"]
    features = result["features"]
    snapshot = result["snapshot"]
    signal = result["signal"]
    confidence = metrics["probability"] if signal["label"] == "Bullish" else (1 - metrics["probability"] if signal["label"] == "Bearish" else abs(metrics["probability"] - 0.5) * 2)

    st.markdown(
        f"""
        <div class="dashboard-banner">
            <div>
                <p class="banner-label">{result["symbol"]} Forecast Window</p>
                <h2>{result["date_start"].strftime("%d %b %Y")} to {result["date_end"].strftime("%d %b %Y")}</h2>
                <span>{status_chip(signal["label"], signal["class"])} {signal["note"]}</span>
            </div>
            <div class="timestamp-badge">Updated {result["generated_at"].strftime("%d %b %Y, %I:%M %p")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards = st.columns(4)
    with cards[0]:
        stat_card("Current Price", f"${snapshot['close']:.2f}", "Latest close in selected window")
    with cards[1]:
        stat_card("Predicted Trend", signal["label"], "Next-session directional view", signal["class"])
    with cards[2]:
        stat_card("Confidence", f"{confidence * 100:.2f}%", "Model conviction")
    with cards[3]:
        tone = "positive" if snapshot["daily_change_pct"] >= 0 else "negative"
        stat_card("Daily Change", f"{snapshot['daily_change_pct']:.2f}%", "Most recent close-to-close move", tone)

    left, right = st.columns([1.9, 1])
    with left:
        st.plotly_chart(build_candlestick_figure(features, result["symbol"]), use_container_width=True)
    with right:
        st.plotly_chart(build_probability_gauge(metrics["probability"]), use_container_width=True)
        st.markdown(
            f"""
            <div class="note-card">
                <strong>Market Status</strong>
                <p>{signal["note"]}</p>
                <div class="mini-grid">
                    <span>Open <strong>${snapshot['open']:.2f}</strong></span>
                    <span>High <strong>${snapshot['high']:.2f}</strong></span>
                    <span>Low <strong>${snapshot['low']:.2f}</strong></span>
                    <span>Volume <strong>{snapshot['volume'] / 1000000:.2f}M</strong></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    lower = st.columns(2)
    with lower[0]:
        st.plotly_chart(build_rsi_figure(features), use_container_width=True)
    with lower[1]:
        st.plotly_chart(build_macd_figure(features), use_container_width=True)

    latest = features.iloc[-1]
    st.markdown("### Latest Indicator Snapshot")
    st.dataframe(
        pd.DataFrame(
            [
                {"Indicator": "SMA 10", "Value": round(float(latest["SMA_10"]), 2)},
                {"Indicator": "EMA 20", "Value": round(float(latest["EMA_20"]), 2)},
                {"Indicator": "RSI", "Value": round(float(latest["RSI"]), 2)},
                {"Indicator": "MACD", "Value": round(float(latest["MACD"]), 4)},
                {"Indicator": "Signal Line", "Value": round(float(latest["Signal_Line"]), 4)},
                {"Indicator": "Volatility", "Value": round(float(latest["Volatility"]), 4)},
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_stock_comparison_page() -> None:
    comparison = st.session_state.comparison_result
    section_heading(
        "Stock Comparison",
        "Model-ranked buy comparison",
        "Compare multiple tickers with the same ANN-GA workflow and rank which one currently looks strongest to buy.",
    )
    if comparison is None:
        st.info("Use the sidebar to choose at least two stocks, then click Compare Stocks.")
        return

    failures = comparison.get("failures", [])
    if failures:
        st.warning(
            "Some selected stocks could not be compared with Yahoo Finance data and were skipped: "
            + " | ".join(failures)
        )

    ranked = comparison["ranked"]
    best_pick = ranked[0]
    best_metrics = best_pick["metrics"]
    best_signal = best_pick["signal"]

    st.markdown(
        f"""
        <div class="dashboard-banner">
            <div>
                <p class="banner-label">Best Buy Candidate</p>
                <h2>{best_pick["symbol"]}</h2>
                <span>{status_chip(best_signal["label"], best_signal["class"])} Ranked highest for the selected comparison window.</span>
            </div>
            <div class="timestamp-badge">Updated {comparison["generated_at"].strftime("%d %b %Y, %I:%M %p")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cards = st.columns(4)
    with cards[0]:
        stat_card("Buy Score", f"{best_pick['score'] * 100:.2f}", "Weighted model comparison score", best_signal["class"])
    with cards[1]:
        stat_card("Uptrend Probability", format_percent(best_metrics["probability"]), "Model bullish probability")
    with cards[2]:
        stat_card("F1 Score", format_percent(best_metrics["f1_score"]), "Prediction balance quality")
    with cards[3]:
        tone = "positive" if best_pick["snapshot"]["daily_change_pct"] >= 0 else "negative"
        stat_card("Daily Change", f"{best_pick['snapshot']['daily_change_pct']:.2f}%", "Most recent close-to-close move", tone)

    table_rows = [
        {
            "Rank": index,
            "Ticker": item["symbol"],
            "Signal": item["signal"]["label"],
            "Buy Score": round(item["score"] * 100, 2),
            "Uptrend Probability": f"{item['metrics']['probability'] * 100:.2f}%",
            "Accuracy": f"{item['metrics']['accuracy'] * 100:.2f}%",
            "Precision": f"{item['metrics']['precision'] * 100:.2f}%",
            "Recall": f"{item['metrics']['recall'] * 100:.2f}%",
            "F1 Score": f"{item['metrics']['f1_score'] * 100:.2f}%",
            "Daily Change": f"{item['snapshot']['daily_change_pct']:.2f}%",
            "Selected Features": ", ".join(item["metrics"]["best_genome"]["selected_features"]),
        }
        for index, item in enumerate(ranked, start=1)
    ]
    st.markdown("### Ranked Comparison Table")
    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
    st.caption(
        "Buy Score = 70% uptrend probability + 25% model quality (accuracy, precision, recall, F1) + 5% recent positive momentum. "
        "This is a model-based comparison aid, not financial advice."
    )

    compare_cols = st.columns(2)
    with compare_cols[0]:
        st.plotly_chart(build_probability_gauge(best_metrics["probability"]), use_container_width=True)
    with compare_cols[1]:
        st.plotly_chart(build_confusion_matrix_figure(best_metrics["confusion_matrix"]), use_container_width=True)


def render_model_insights() -> None:
    result = st.session_state.analysis_result
    section_heading("Model Insights", "How the hybrid ANN-GA engine is making its call", "Inspect optimization output, model quality, and the architecture path from indicators to classification.")
    if result is None:
        st.info("Run a prediction first to populate training metrics and diagnostic visuals.")
        return

    metrics = result["metrics"]
    genome = metrics["best_genome"]
    top = st.columns([1.2, 1])
    with top[0]:
        st.markdown(
            """
            <div class="architecture-card">
                <p class="architecture-label">ANN-GA Architecture Overview</p>
                <div class="architecture-flow">
                    <div><strong>Market Data</strong><span>OHLCV time series</span></div>
                    <div><strong>Feature Engine</strong><span>SMA, EMA, RSI, MACD, volatility</span></div>
                    <div><strong>Genetic Algorithm</strong><span>Feature mask plus hyperparameter search</span></div>
                    <div><strong>ANN Classifier</strong><span>Binary UP or DOWN prediction</span></div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with top[1]:
        st.plotly_chart(build_confusion_matrix_figure(metrics["confusion_matrix"]), use_container_width=True)

    row = st.columns(4)
    with row[0]:
        stat_card("Accuracy", format_percent(metrics["accuracy"]), "Holdout quality")
    with row[1]:
        stat_card("Precision", format_percent(metrics["precision"]), "Positive prediction quality")
    with row[2]:
        stat_card("Recall", format_percent(metrics["recall"]), "Positive class capture")
    with row[3]:
        stat_card("F1 Score", format_percent(metrics["f1_score"]), "Balanced metric")

    bottom = st.columns([1.05, 1])
    with bottom[0]:
        st.markdown("### Optimization Outcome")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Setting": "Hidden layer size", "Value": genome["hidden_layer_size"]},
                    {"Setting": "Activation", "Value": genome["activation"]},
                    {"Setting": "Learning rate", "Value": genome["learning_rate_init"]},
                    {"Setting": "Selected features", "Value": ", ".join(genome["selected_features"])},
                    {"Setting": "Training samples", "Value": metrics["training_samples"]},
                    {"Setting": "Test samples", "Value": metrics["test_samples"]},
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
    with bottom[1]:
        st.markdown(
            """
            <div class="note-card">
                <strong>What the GA contributes</strong>
                <p>The genetic algorithm searches across feature subsets and ANN settings, helping the model avoid a one-size-fits-all configuration.</p>
            </div>
            <div class="note-card">
                <strong>What the ANN contributes</strong>
                <p>The neural network captures non-linear interactions between momentum, trend, and volatility signals to classify the next-session direction.</p>
            </div>
            <div class="note-card">
                <strong>Use case</strong>
                <p>This is a decision-support system. It is strongest when combined with broader research, position sizing, and risk controls.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_history_page() -> None:
    _, mongo_service = get_services()
    mongo_error = getattr(mongo_service, "error_message", "")
    section_heading("History / Logs", "Search previous predictions from MongoDB Atlas", "Use ticker and date filters to review stored runs and audit how the system has behaved across time.")
    if not mongo_service.available:
        st.warning("MongoDB Atlas is not connected. Update your `.env` connection string and restart the app.")
        if mongo_error:
            st.code(mongo_error)
        return

    cols = st.columns([1, 1, 0.8])
    with cols[0]:
        ticker_filter = st.text_input("Filter by ticker", value="", help="Leave empty to show all stored tickers.")
    with cols[1]:
        history_range = st.date_input("Filter by created date", value=(date.today() - timedelta(days=30), date.today()), help="Search based on the time when predictions were generated.")
    with cols[2]:
        if st.button("Search Logs", use_container_width=True):
            st.rerun()

    start_date, end_date = get_date_bounds(history_range)
    records = mongo_service.search_predictions(symbol=ticker_filter or None, start_date=datetime.combine(start_date, time.min), end_date=datetime.combine(end_date, time.max), limit=100)
    if not records:
        st.info("No stored predictions match the current filters yet.")
        return

    frame = pd.DataFrame(records)
    frame["created_at"] = pd.to_datetime(frame["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
    st.dataframe(
        frame[["symbol", "predicted_trend", "bullish_probability", "validation_accuracy", "precision", "recall", "f1_score", "created_at"]].rename(
            columns={
                "symbol": "Ticker",
                "predicted_trend": "Trend",
                "bullish_probability": "Uptrend Probability",
                "validation_accuracy": "Accuracy",
                "precision": "Precision",
                "recall": "Recall",
                "f1_score": "F1 Score",
                "created_at": "Generated At",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    latest_record = records[0]
    detail = st.columns([1, 1.1])
    with detail[0]:
        selected_features = ", ".join(latest_record["best_genome"]["selected_features"])
        st.markdown(
            f"""
            <div class="note-card">
                <strong>Latest Stored Run</strong>
                <div class="history-grid">
                    <span>Ticker <strong>{latest_record["symbol"]}</strong></span>
                    <span>Trend <strong>{latest_record["predicted_trend"]}</strong></span>
                    <span>Accuracy <strong>{latest_record["validation_accuracy"]}</strong></span>
                    <span>Features <strong>{selected_features}</strong></span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with detail[1]:
        st.markdown(
            f"""
            <div class="note-card">
                <strong>Recent Decision Summary</strong>
                <p>The latest stored forecast for <strong>{latest_record["symbol"]}</strong> was classified as <strong>{latest_record["predicted_trend"]}</strong>.</p>
                <p>Generated at {latest_record["created_at"]} with accuracy {latest_record["validation_accuracy"]} and F1 score {latest_record["f1_score"]}.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_about_page() -> None:
    section_heading("About Project", "Why a hybrid ANN-GA system is useful for market decision support", "The project blends technical indicators, optimization, and non-linear classification inside a premium Streamlit interface.")
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown(
            """
            <div class="note-card">
                <strong>Hybrid ANN-GA approach</strong>
                <p>The model engineers features from historical price and volume data, then uses a genetic algorithm to search for a strong feature subset and ANN configuration. The selected neural network predicts whether the next market move is more likely to be up or down.</p>
            </div>
            <div class="note-card">
                <strong>Why it helps</strong>
                <p>Financial markets are noisy and non-linear. A GA expands the search beyond manual tuning, while the ANN can model complex relationships between momentum, volatility, and trend indicators.</p>
            </div>
            <div class="note-card">
                <strong>Best use</strong>
                <p>This system is intended to support analysis and consistency. It helps users compare signals, measure model quality, and preserve decision history over time.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            """
            <div class="about-grid">
                <div><span>Data Source</span><strong>Yahoo Finance via yfinance</strong></div>
                <div><span>Database</span><strong>MongoDB Atlas</strong></div>
                <div><span>Model</span><strong>MLP ANN + Genetic search</strong></div>
                <div><span>Charts</span><strong>Plotly candlestick, RSI, MACD</strong></div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    initialize_state()
    load_styles()
    render_shell_header()
    render_top_navigation()
    controls = render_sidebar()
    if controls["predict_clicked"]:
        run_prediction(controls)
    if controls["compare_clicked"]:
        run_comparison(controls)

    if st.session_state.active_page == "Landing":
        render_landing_page()
    elif st.session_state.active_page == "Prediction Dashboard":
        render_prediction_dashboard()
    elif st.session_state.active_page == "Stock Comparison":
        render_stock_comparison_page()
    elif st.session_state.active_page == "Model Insights":
        render_model_insights()
    elif st.session_state.active_page == "History / Logs":
        render_history_page()
    else:
        render_about_page()


if __name__ == "__main__":
    main()
