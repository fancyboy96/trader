import yfinance as yf
import pandas as pd

TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

def fetch_ticker_summary(symbol: str) -> dict:
    t = yf.Ticker(symbol)
    info = t.info
    return {
        "symbol": symbol,
        "name": info.get("longName", "N/A"),
        "price": info.get("currentPrice") or info.get("regularMarketPrice", "N/A"),
        "market_cap": info.get("marketCap", "N/A"),
        "pe_ratio": info.get("trailingPE", "N/A"),
        "52w_high": info.get("fiftyTwoWeekHigh", "N/A"),
        "52w_low": info.get("fiftyTwoWeekLow", "N/A"),
    }

def main():
    print(f"Fetching data for: {', '.join(TICKERS)}\n")
    rows = [fetch_ticker_summary(sym) for sym in TICKERS]
    df = pd.DataFrame(rows).set_index("symbol")
    df["market_cap"] = df["market_cap"].apply(
        lambda x: f"${x/1e12:.2f}T" if isinstance(x, (int, float)) and x >= 1e12
        else (f"${x/1e9:.2f}B" if isinstance(x, (int, float)) else x)
    )
    df["price"] = df["price"].apply(lambda x: f"${x:.2f}" if isinstance(x, (int, float)) else x)
    df["pe_ratio"] = df["pe_ratio"].apply(lambda x: f"{x:.1f}" if isinstance(x, (int, float)) else x)
    print(df.to_string())

if __name__ == "__main__":
    main()
