<<<<<<< HEAD
# MarketPulse AI

MarketPulse AI is a professional Streamlit web application for stock market trend prediction using a hybrid Artificial Neural Network and Genetic Algorithm workflow. The system downloads market data, engineers technical indicators, optimizes ANN settings with a GA, predicts bullish, bearish, or neutral direction, and stores prediction history in MongoDB Atlas.

## Features

- Premium Streamlit interface inspired by modern trading platforms
- Landing, dashboard, model insights, history, and about sections
- Hybrid ANN-GA prediction engine for next-session trend forecasting
- Technical indicators including RSI, MACD, moving averages, momentum, and volatility
- MongoDB Atlas backed prediction history for persistence and review
- Plotly candlestick, RSI, MACD, probability gauge, and confusion matrix visuals

## Project Structure

```text
.
|-- app.py
|-- requirements.txt
|-- styles.css
|-- .env.example
|-- services
|   |-- __init__.py
|   |-- config.py
|   |-- data_service.py
|   |-- db_service.py
|   `-- model_service.py
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and adjust MongoDB settings if needed.
4. Make sure MongoDB is running locally or update `MONGO_URI` for your cluster.
5. Start the Streamlit app:

```bash
streamlit run app.py
```

## MongoDB Collection

The application stores prediction runs in the `predictions` collection with:

- Stock symbol
- Predicted trend
- Bullish probability
- Validation accuracy
- Optimized GA genome details
- Latest market snapshot
- Timestamp

## Important Note

This project is a decision-support prototype for academic and demonstration use. Stock predictions are inherently uncertain and should not be treated as financial advice.
=======
# Stock-Market-Trend-Prediction-System
>>>>>>> 26f26b68d2e146098e722206b31b352e0eff036e
