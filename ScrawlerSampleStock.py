# pip install lxml
from csv import writer
from datetime import datetime
from io import StringIO
import os
import traceback
from turtle import pd


def check_import(module_name, alias=None):
    try:
        module = __import__(module_name)

        if alias:
            globals()[alias] = module
        else:
            globals()[module_name] = module

    except ImportError:
        print(f"請先安裝 {module_name}")
        exit()


check_import("os")
check_import("requests")
check_import("urllib3")
check_import("numpy", "np")
check_import("pandas", "pd")
check_import("datetime")
check_import("yfinance", "yf")
check_import("warnings")
check_import("traceback")
check_import("sys")
check_import ("lxml") # pd.read_html 需要的解析器
check_import ("wcwidth")
check_import ("openpyxl")

from io import StringIO # 不直接把整個 io 套件 import 進來，只 import 其中一個 function


warnings.filterwarnings('ignore') # 關掉幾乎所有 Python warning
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # 關掉 urllib3 的 HTTPS warning

print("="*70) # 印出 70 個 =
print("   任務：掃描台股全市場，尋找 AI 7 大動能極限飆股")
print("   核心：捨棄 RSI/MACD/成交量，純粹依賴價格破壞力與波動率")
print("   視野：跨市場百分比排名 (Percentile Rank)")
print("="*70)

def save_stock_list(stock_dict):
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop") # 目前使用者的 home directory，就是 C:\Users\{username}，然後再加上 Desktop 就是桌面路徑
        csv_filename = os.path.join(desktop_path, "TW_Stock_List_.csv")
        df_stock_list = pd.DataFrame.from_dict(stock_dict, orient='index')
        df_stock_list.index.name = 'ID'
        df_stock_list.reset_index(inplace=True)
        df_stock_list.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        print(f"台股清單已儲存至桌面：{csv_filename}")
    except:
        print("無法儲存 CSV 檔案至桌面，請確認權限。")

def get_tw_stock_list():
    print("[1/3] 抓取全台股清單 (上市+上櫃+興櫃)...")
    stock_dict = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        for Page in [2, 4, 5]: # in (2, 5) 才是 2、3、4
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={Page}"
            res = requests.get(url, headers=headers, verify=False, timeout=15)
            df = pd.read_html(StringIO(res.text), flavor="lxml")[0].iloc[2:] # df = dataframe     
            for index, row in df.iterrows(): # 逐 row 讀取 DataFrame，每次回傳 (index, row)，但我們不需要 index，所以用 _ 代替
                try:
                    code_name = str(row[0]).split()
                    print(f"{code_name}...", end='\r')
                    if len(code_name) == 2:
                        code, name = code_name
                        cat = str(row[3]) # category
                        if len(code) == 4:
                            if cat in ['上市', '上櫃', '興櫃']:
                                suffix = ".TW" if cat == '上市' else ".TWO"
                                stock_dict[f"{code}{suffix}"] = {"name": name, "ind": cat} # "": key, : value 
                except Exception as e:
                    print(f"row error: {type(e).__name__}")
    except Exception as e: 
        print(f"抓取清單失敗: {type(e).__name__}")

    save_stock_list(stock_dict)
    return stock_dict

def history_volatility(close_prices):
    # day1_close = 100, day2_close = 110, pct_change = (110 - 100) = 10%
    # daily return: 每日報酬率
    daily_ret = close_prices.pct_change()
    # std: 標準差，看資料有多分散
    hist_vol = daily_ret.rolling(20).std().iloc[-1] * np.sqrt(252) * 100
    return hist_vol

def moving_average(close_prices, window):
    # rolling: 每次看連續 5 天收盤價，[100 102 101 105 107]
    # mean(): 算平均
    # iloc[-1]: 最後一 row
    return close_prices.rolling(window).mean().iloc[-1]

def bollinger_band_width(close_prices): # 布林通道，價格大部分時間應該待在通道裡
    ma20 = close_prices.rolling(20).mean() 
    std20 = close_prices.rolling(20).std() # 最近20天價格的標準差
    bb_upper = ma20 + 2 * std20
    bb_lower = ma20 - 2 * std20
    return ((bb_upper - bb_lower) / ma20 * 100).iloc[-1] # 4 * std20 / ma20 * 100

def price_to_bollinger_upper (close_prices):
    ma20 = close_prices.rolling(20).mean() 
    std20 = close_prices.rolling(20).std()
    current_close = close_prices.iloc[-1] # 取今日(就是最後一個)收盤價
    bb_upper = ma20 + 2 * std20

    return (current_close / bb_upper.iloc[-1] - 1) * 100

def record_add(records_db, Name, Id, close_prices, following_day_price):

    ma5 = moving_average(close_prices, 5)
    ma20 = moving_average(close_prices, 20)
    ma60 = moving_average(close_prices, 60)
    current_close = close_prices.iloc[-1]

    # 特徵 1: 歷史波動率
    hist_vol = history_volatility(close_prices)
    # 特徵 2: 布林通道寬度
    bb_width = bollinger_band_width(close_prices)
    # 特徵 3: 股價距離 MA60 幾 %
    p_to_ma60 = (current_close / ma60 - 1) * 100
    # 特徵 4: 短均線 vs 長均線 強度
    trend_str = (ma5 / ma60 - 1) * 100
    # 特徵 5: 股價距離 MA20 幾 %
    p_to_ma20 = (current_close / ma20 - 1) * 100
    # 特徵 6: 股價距離布林通道上緣幾 %
    p_to_bbupper = price_to_bollinger_upper(close_prices)
    # 特徵 7: 10 日價格變動率
    roc_10 = (current_close - close_prices.iloc[-11]) / close_prices.iloc[-11] * 100
    
    # 檢查 hist_vol 或 roc_10 是不是 NaN
    if np.isnan(hist_vol) or np.isnan(roc_10): return 

    records_db.append({
        'ID': Id,
        'Name': Name,
        'Close': current_close,
        'MA5': ma5,
        'HistoryVol': hist_vol,
        'BBWidth': bb_width,
        'PriceToMA60': p_to_ma60,
        'Strength': trend_str,
        'PriceToMA20': p_to_ma20,
        'PriceToBBUpper': p_to_bbupper,
        'ROC_10': roc_10,
        'FollowingDayPrice': following_day_price
    })

def top_20_extract(df):
    features = ['HistoryVol', 'BBWidth', 'PriceToMA60', 'Strength', 'PriceToMA20', 'PriceToBBUpper', 'ROC_10']
    weights = [29.08, 19.33, 10.39, 7.67, 7.26, 5.09, 4.25]

    # 計算 PR 值 (0~1)，不直接排名 1、2、3...，是因為每天符合條件的股票數量不一樣，例如上下架
    for f in features:
        df[f + '_Rank'] = df[f].rank(pct=True)

    # 乘以權重
    df['Score'] = 0.0
    for f, w in zip (features, weights): 
        df['Score'] += df[f + '_Rank'] * w

    # 正規化為 100 分制
    max_score = sum(weights)
    df['Score'] = (df['Score'] / max_score) * 100

    # 當下收盤價必須站上 5MA
    df_filtered = df[df['Close'] >= df['MA5']].copy()
    top20 = df_filtered.sort_values(by='Score', ascending=False).head(20)
    
    return top20

def pad(text, width):
    text = str(text)
    return text + " " * max(width - wcwidth.wcswidth(text), 0)

def top_20_dump(date, top20):
    
    print("\n" + "="*80)
    print(f"{date} TOP 20 名單")
    print("="*80)
    print(f"{pad('排名', 10)} |"
          f"{pad('代號', 10)} |"
          f"{pad('股名', 10)} |"
          f"{pad('收盤價', 10)} |"
          f"{pad('AI 分數', 10)} |"
          f"{pad('次日最高價', 10)}")
    print("-" * 80)

    for rank, (_, row) in enumerate(top20.iterrows(), 1):
        score = f"{row['Score']:.2f}"
        close = f"{row['Close']:.2f}"
        following_day_price = f"{row['FollowingDayPrice']:.2f}" if not pd.isna(row['FollowingDayPrice']) else "N/A"
        print(f"{pad(rank, 10)} |"
              f"{pad(row['ID'], 10)} |"
              f"{pad(row['Name'], 10)} |"
              f"{pad(close, 10)} |"
              f"{pad(score, 10)} |"
              f"{pad(following_day_price, 10)}")
        
    print("="*80)
    print("前 7 檔優先分配資金，跌破 MA5 第二天未站回無條件停損\n")


def top_20_save(date, top20, writer):
    try:

        columns_to_save = [
            'ID',
            'Name',
            'Close',
            'Score',
            'HistoryVol',
            'BBWidth',
            'PriceToMA60',
            'Strength',
            'PriceToMA20',
            'PriceToBBUpper',
            'ROC_10'
        ]

        sheet_name = date.strftime("%Y-%m-%d")
        top20[columns_to_save].to_excel(writer, sheet_name=sheet_name, index=False)
        ws = writer.sheets[sheet_name]

        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter # 第一個 cell 屬於哪的 col，其實就是 col 本人 title

            for cell in col:
                try:
                    cell_length = len(str(cell.value))
                    if cell_length > max_length:
                        max_length = cell_length # 找最長的那個當作這整欄的寬度
                except:
                    pass

            adjusted_width = max_length + 4
            ws.column_dimensions[column_letter].width = adjusted_width

    except:
        traceback.print_exc()

def output_results(writer, date, records):
    df_res = pd.DataFrame(records)
    if df_res.empty:
        print("沒有足夠的資料可以運算。")
        return
    top20 = top_20_extract(df_res)
    top_20_dump(date, top20)
    top_20_save(date, top20, writer)

def main():
    stock_dict = get_tw_stock_list()
    print(f"取得標的共 {len(stock_dict)} 檔。")
    print("[2/3] 開始全市場掃描與數據下載...")
    
    all_tickers = list(stock_dict.keys()) # 把 stock_dict 裡所有的 key 取出來，轉成 list
    batch_size = 50
    records_today = []
    records_yesterday = []
    records_2_days_ago = []
    records_3_days_ago = []
    records_4_days_ago = []

    date_today = datetime.datetime.now().date()
    date_yesterday = date_today - datetime.timedelta(days=1)
    date_2_days_ago = date_today - datetime.timedelta(days=2)
    date_3_days_ago = date_today - datetime.timedelta(days=3)
    date_4_days_ago = date_today - datetime.timedelta(days=4)
    
    
    # 批次下載歷史資料
    for i in range(0, len(all_tickers), batch_size): # e.g., range (0, 5, 2) 會回傳 0, 2, 4
        batch = all_tickers[i:i+batch_size]
        print(f"   下載進度: {min(i+batch_size, len(all_tickers))}/{len(all_tickers)}...", end='\r')
        
        try:
            # 抓取 100 天確保 60MA 計算正確
            data = yf.download(batch, period="100d", interval="1d", group_by='ticker', auto_adjust=False, progress=False, threads=True)
            date = ["today", "yesterday", "2_days_ago", "3_days_ago", "4_days_ago"]

            for ticker in batch: # ticker = {code}{suffix}
                following_day_price = None
                try:
                    df = data[ticker] if len(batch) > 1 else data
                    if df.empty or len(df) < 60: continue # 資料不到 60 天
                    df = df.dropna() # 把含有缺失值（NaN）的 row 刪掉
                    
                    for d in date:
                        close = df['Close'] # 確認收盤價至少有 60 筆
                        if len(close) < 60: continue
                        records = locals().get(f"records_{d}") # 從目前 scope 的 local variables 裡，取出名字叫做 records_xxx 的變數
                        record_add(records, stock_dict[ticker]['name'], ticker.replace(".TW", "").replace(".TWO", ""), close, following_day_price)
                        following_day_price = df.iloc[-1]['High']
                        df = df.iloc[:-1]
                    
                except: continue
        except: pass

    print("\n資料下載完成！")
    print("[3/3] 正在執行 AI 權重運算與全市場 PR 值排名...")
    
    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    xlsx_filename = os.path.join(desktop_path, f"Top20_{timestamp}.xlsx")
    with pd.ExcelWriter(xlsx_filename, engine='openpyxl') as writer:
        output_results(writer, date_today, records_today)
        output_results(writer, date_yesterday, records_yesterday)
        output_results(writer, date_2_days_ago, records_2_days_ago)
        output_results(writer, date_3_days_ago, records_3_days_ago)
        output_results(writer, date_4_days_ago, records_4_days_ago)   
    
    print(f"Excel 已儲存至桌面：{xlsx_filename}")
    input("程式執行完畢，請按 Enter 鍵關閉視窗...")

if __name__ == "__main__": # python code 的 entry point
    try:
        main()
    except Exception as e:
        print("\n" + "!"*60)
        print("程式執行中發生錯誤：")
        traceback.print_exc()
        print("!"*60)
        input("Enter 鍵關閉視窗...")