# MarketPulse AI

MarketPulse AI is a Streamlit-based stock analysis application that combines technical indicators, a Genetic Algorithm (GA), and an Artificial Neural Network (ANN) to estimate short-term market direction. The project supports single-stock forecasting, multi-stock comparison, interactive visual dashboards, and MongoDB-backed prediction history.

## What This Project Does

The application helps users:

- fetch historical stock data from Alpha Vantage
- upload offline CSV data for analysis
- engineer technical indicators such as SMA, EMA, RSI, MACD, volatility, momentum, and volume trend
- run a hybrid GA + ANN workflow to predict the next-session direction
- compare multiple stocks and rank which one currently looks stronger to buy
- store prediction runs and review them later through MongoDB

## Core Features

- Streamlit dashboard with landing, prediction, comparison, model insights, history, and about pages
- Hybrid ANN + GA model for binary trend prediction
- Technical analysis indicator pipeline built with pandas and numpy
- Plotly visualizations including candlestick, RSI, MACD, confusion matrix, and probability gauge
- Stock comparison workflow that ranks multiple tickers with a model-based buy score
- MongoDB Atlas integration for storing prediction history
- Optional CSV upload support for offline demos or testing
- Alpha Vantage data retrieval for live market history

## Tech Stack

- Python
- Streamlit
- pandas
- numpy
- scikit-learn
- Plotly
- yfinance
- pymongo
- python-dotenv

## Project Structure

```text
.
|-- app.py
|-- requirements.txt
|-- styles.css
|-- .env.example
|-- README.md
|-- services
|   |-- __init__.py
|   |-- config.py
|   |-- data_service.py
|   |-- db_service.py
|   `-- model_service.py
|-- sample_RELIANCE_NS.csv
|-- nse_INFY.csv
|-- nse_RELIANCE.csv
|-- nse_TCS.csv
|-- real_AAPL.csv
`-- real_TSLA.csv
```

## How The Workflow Operates

1. The user selects a ticker or uploads a CSV file.
2. Historical OHLCV data is loaded from Alpha Vantage or from the uploaded file.
3. Technical indicators are generated from the raw price data.
4. The model creates a target label based on whether the next closing price is higher than the current one.
5. A Genetic Algorithm searches for a strong feature subset and neural-network configuration.
6. An `MLPClassifier` is trained on the selected feature set.
7. The app displays prediction probability, metrics, and charts.
8. The result can be stored in MongoDB for later review.

## Pages In The Application

### Landing

Introduces the platform, the ANN + GA workflow, and the key features of the dashboard.

### Prediction Dashboard

Runs a single-stock forecast and displays:

- predicted trend
- confidence / probability
- current market snapshot
- candlestick chart
- RSI and MACD charts
- latest indicator values

### Stock Comparison

Compares multiple selected tickers using the same model pipeline and ranks them using a weighted buy score based on:

- uptrend probability
- model quality metrics
- recent positive momentum

### Model Insights

Shows:

- accuracy
- precision
- recall
- F1 score
- confusion matrix
- selected features
- best GA-selected model settings

### History / Logs

Loads prediction records from MongoDB and lets the user review past runs.

### About Project

Explains the purpose of the hybrid model and the overall system design.

## Machine Learning Approach

The project uses a hybrid approach:

- Genetic Algorithm:
  searches for a useful subset of engineered features and a promising neural-network setup
- Artificial Neural Network:
  uses scikit-learn's `MLPClassifier` to classify whether the next move is likely up or down

### Input Features

The model works with these engineered indicators:

- Return
- SMA 10
- SMA 20
- EMA 10
- EMA 20
- Momentum 5
- Volatility
- RSI
- MACD
- Signal Line
- Volume Trend

### Output

The model predicts a binary class:

- `1`: next close is higher than the current close
- `0`: next close is not higher than the current close

## Setup Instructions

### 1. Clone the repository

```bash
git clone https://github.com/anivish2004/Stock-Market-Trend-Prediction-System.git
cd Stock-Market-Trend-Prediction-System
```

### 2. Create and activate a virtual environment

Windows PowerShell:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and set your values.

Example:

```env
MONGO_URI=mongodb+srv://<username>:<password>@<cluster-url>/<database>?retryWrites=true&w=majority
MONGO_DB_NAME=your_database_name
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key
```

Notes:

- `MONGO_URI` and `MONGO_DB_NAME` are needed for history storage
- `ALPHA_VANTAGE_API_KEY` is required for live market data

### 5. Run the app

```bash
streamlit run app.py
```

## Sample Data Files

The repository includes CSV files that can be used for offline testing or demonstrations:

- `sample_RELIANCE_NS.csv`
- `nse_INFY.csv`
- `nse_RELIANCE.csv`
- `nse_TCS.csv`
- `real_AAPL.csv`
- `real_TSLA.csv`

These files should contain columns such as:

- `Date`
- `Open`
- `High`
- `Low`
- `Close`
- `Adj Close`
- `Volume`

## MongoDB Storage

When MongoDB is available, the application stores prediction runs in the `predictions` collection. Stored data includes:

- stock symbol
- selected date range
- predicted trend
- bullish probability
- validation metrics
- best genome settings
- confusion matrix
- market snapshot
- feature snapshot
- creation timestamp

## Important Notes

- This project is intended for educational, academic, and demonstration purposes.
- Stock market behavior is noisy and uncertain, so the output should be treated as decision support rather than financial advice.
- The current model-selection flow uses a holdout split during optimization, which is suitable for a prototype but can be improved further for stricter evaluation.

## Future Improvements

- walk-forward validation for time-series evaluation
- better convergence handling for the neural network
- risk-adjusted comparison ranking
- exportable reports for predictions and comparisons
- richer model explainability

## Author

Created and maintained as a stock market trend prediction system using Streamlit, machine learning, and MongoDB.
