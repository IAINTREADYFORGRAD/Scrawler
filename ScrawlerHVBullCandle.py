import pandas as pd
import yfinance as yf
import requests
import warnings
import urllib3
import traceback
import wcwidth

from io import StringIO

warnings.filterwarnings('ignore')
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_tw_stock_list():
    headers = {"user-agent": "Mozilla/5.0"}
    stock_dict = {}
    try: 
        for Page in [2, 4, 5]:
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={Page}"
            res = requests.get(url, headers=headers, verify=False, timeout=15)
            df = pd.read_html(StringIO(res.text), flavor="lxml")[0].iloc[2:]
            for index, row in df.iterrows():
                try:
                    code_name = str(row[0]).split()
                    if len(code_name) == 2:
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
    today_close = df['Close'].iloc[-1]
    today_open = df['Open'].iloc[-1]
    
    return today_close > today_open

def is_high_volume(df):
    yesterday_volume = df['Volume'].iloc[-2]
    today_volume = df['Volume'].iloc[-1]
    
    return today_volume > yesterday_volume * 2

def add_records (records_db, name, ticker, df):

    records_db[ticker] = {
        "ID": ticker,
        "name": name,
        "today_close": df['Close'].iloc[-1],
        "today_open": df['Open'].iloc[-1],
        "yesterday_volume": df['Volume'].iloc[-2],
        "today_volume": df['Volume'].iloc[-1],
        "vol_ratio": df['Volume'].iloc[-1] / df['Volume'].iloc[-2] if df['Volume'].iloc[-2] != 0 else 0
    }


def high_vol_bull_candles_extract (stock_list):

    batch_size = 50

    # stock_list: dict
    # stock_list.keys() 轉成 list
    ticker_list = list(stock_list.keys()) 

    # nested dict
    # high_volume_bull_candles = {
    #     "2330": {
    #         "volume": 50000,
    #         "close": 1020
    #     }
    # }
    high_volume_bull_candles = {} 
    
    try:
        for i in range(0, len(ticker_list), batch_size):
            batch = ticker_list[i:i+batch_size] 
            data = yf.download(batch, period="100d", interval="1d", group_by='ticker', auto_adjust=False, progress=False, threads=True)
            
            for ticker in batch:
                df = data[ticker] if len(batch) > 1 else data
                if df.empty:
                    continue
                df = df.dropna()
                
                if (is_bull_candle(df)) and (is_high_volume(df) and df['Volume'].iloc[-1] > 1000):
                    add_records(high_volume_bull_candles, stock_list[ticker]["name"], ticker, df)

    except Exception as e:
        print(f"Error processing batch: {e}")

    return high_volume_bull_candles

def pad(text, width):
    text = str(text)
    return text + " " * max(width - wcwidth.wcswidth(text), 0)

def top_20_dump (top_20):
    date = pd.Timestamp.now().strftime("%Y-%m-%d")
    print("\n" + "="*105)
    print(f"{date} TOP 20 名單")
    print("="*105)
    print(f"{pad('排名', 10)} |"
          f"{pad('代號', 10)} |"
          f"{pad('股名', 10)} |"
          f"{pad('今日開盤價', 10)} |"
          f"{pad('今日收盤價', 10)} |"
          f"{pad('昨日成交量', 10)} |"
          f"{pad('今日成交量', 10)} |"
          f"{pad('成交量倍數', 10)} |"
          )
    print("-" * 105)

    # enumerate: 會把 top_20 一個一個拿出來，default 是將 index (這裡是 rank) 設為 0
    # start = 1，即是將 rank 從 1 開始
    for rank, (ticker, data) in enumerate(top_20, start=1):
        today_close = f"{data['today_close']:.2f}"
        today_open = f"{data['today_open']:.2f}"
        yesterday_volume = f"{data['yesterday_volume']}"
        today_volume = f"{data['today_volume']}"
        vol_ratio = f"{data['vol_ratio']:.2f}"
        print(f"{pad(rank, 10)} |"
              f"{pad(ticker, 10)} |"
              f"{pad(data['name'], 10)} |"
              f"{pad(today_open, 10)} |"
              f"{pad(today_close, 10)} |"
              f"{pad(yesterday_volume, 10)} |"
              f"{pad(today_volume, 10)} |"
              f"{pad(vol_ratio, 10)}")
        
    print("="*105)



def main():
    
    stock_list = get_tw_stock_list()
    print(f"Total stocks fetched: {len(stock_list)}")

    high_vol_bull_candles = high_vol_bull_candles_extract (stock_list)

    # .items(): {key: value} -> (key, value)
    # high_vol_bull_candles.items()
    # (
    #   "2330",                     -> item[0]
    #   {                           -
    #        "today_close": 1000,    |-item[1]
    #        "today_open": 1010,     |
    #       "vol_ratio": 3.5        -
    #   }
    # )
    top_20 = sorted(high_vol_bull_candles.items(), key=lambda x: x[1]['vol_ratio'], reverse=True)[:20]

    # 注意，top_20 不是 list of dict，而是 list of tuples
    # top_20 = [
    #     ("2330", {"today_close": 1000, "today_open": 1010, "vol_ratio": 3.5}),
    #     ("2317", {"today_close": 50, "today_open": 55, "vol_ratio": 2.8}),
    #     ...       
    # ] 
    top_20_dump(top_20)                     

if __name__ == "__main__": # python code 的 entry point
    try:
        main()
    except Exception as e:
        print("\n" + "!"*60)
        print("程式執行中發生錯誤：")
        traceback.print_exc()
        print("!"*60)
        input("Enter 鍵關閉視窗...")




    
    

    