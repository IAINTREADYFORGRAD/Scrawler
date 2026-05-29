import pandas as pd
import yfinance as yf
import requests
import warnings
import urllib3

from io import StringIO

warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_tw_stock_list():
    headers = {"user-agent": "Mozilla/5.0"}
    stock_dict = []
    try: 
        for Page in [2, 4, 5]:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={Page}"
            res = requests.get(url, headers=headers, verify=False, timeout=15)
            df = pd.read_html(StringIO(res.text), flavor="lxml")[0].iloc[2:]
            for index, row in df.iterrows():
                try:
                    code_name = str(row[0]).split()
                    code, name = code_name
                    cat = str(row[3])
                    if cat in ["上市", "上櫃", "興櫃"]:
                        suffix = ".TW" if cat == '上市' else ".TWO"
                        stock_dict[f"{code}{suffix}"] = {"name": name, "ind": cat}
                except Exception as e:
                    print(f"Error processing row: {row} - {e}")
    except Exception as e:
        print(f"Error fetching stock list: {e}")
    return stock_dict

def is_bull_candle(df):
    yesterday_close = df['Close'].iloc[-2]
    today_open = df['Open'].iloc[-1]
    
    return today_open > yesterday_close

def is_high_volume(df):
    yesterday_volume = df['Volume'].iloc[-2]
    today_volume = df['Volume'].iloc[-1]
    
    return today_volume > yesterday_volume * 2

def add_records (records_db, ticker, df):
    records_db[ticker] = {
        "yesterday_close": df['Close'].iloc[-2],
        "today_open": df['Open'].iloc[-1],
        "yesterday_volume": df['Volume'].iloc[-2],
        "today_volume": df['Volume'].iloc[-1]
    }

    


def main():
    batch_size = 50
    high_volume_bull_candles = {}

    stock_list = get_tw_stock_list()
    print(f"Total stocks fetched: {len(stock_list)}")
    

    try:
        for i in range (0, len(stock_list), batch_size):
            batch = list(stock_list.keys())[i:i+batch_size]
            data = yf.download(batch, period="100d", interval="1d", group_by='ticker', auto_adjust=False, progress=False, threads=True)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty:
                    continue
                df = df.dropna()
                
                if (is_bull_candle(df)) and (is_high_volume(df)):
                    high_volume_bull_candles[ticker] = stock_list[ticker]