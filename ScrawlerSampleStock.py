# pip install lxml
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


# warnings.filterwarnings('ignore') # 關掉幾乎所有 Python warning
# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # 關掉 urllib3 的 HTTPS warning

print("="*70) # 印出 70 個 =
print("   任務：掃描台股全市場，尋找 AI 7 大動能極限飆股")
print("   核心：捨棄 RSI/MACD/成交量，純粹依賴價格破壞力與波動率")
print("   視野：跨市場百分比排名 (Percentile Rank)")
print("="*70)

def get_tw_stock_list():
    print("[1/3] 抓取全台股清單 (上市+上櫃)...")
    stock_dict = {}
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        for Page in [2, 4, 5]: # in (2, 5) 才是 2、3、4
            url = f"https://isin.twse.com.tw/isin/C_public.jsp?strMode={Page}"
            res = requests.get(url, headers=headers, verify=False, timeout=15)
            df = pd.read_html(res.text)[0].iloc[1:] # df = dataframe
            for index, row in df.iterrows(): # 逐 row 讀取 DataFrame，每次回傳 (index, row)，但我們不需要 index，所以用 _ 代替
                try:
                    code_name = str(row[0]).split()
                    if len(code_name) == 2:
                        code, name = code_name
                        cat = str(row[3]) # category
                        if len(code) == 4:
                            if cat in ['上市', '上櫃', '興櫃']:
                                suffix = ".TW" if Page == 2 else ".TWO"
                                stock_dict[f"{code}{suffix}"] = {"name": name, "ind": cat} # "": key, : value 
                except: continue
    except Exception as e: 
        print(f"抓取清單失敗: {e}") # f: 直接在字串裡放變數
    return stock_dict

def history_volatility(close_price):
    # day1_close = 100, day2_close = 110, pct_change = (110 - 100) = 10%
    # daily return: 每日報酬率
    daily_ret = close_price.pct_change()
    # std: 標準差，看資料有多分散
    hist_vol = daily_ret.rolling(20).std().iloc[-1] * np.sqrt(252) * 100
    return hist_vol

def moving_average(close_price, window):
    # rolling: 每次看連續 5 天收盤價，[100 102 101 105 107]
    # mean(): 算平均
    # iloc[-1]: 最後一 row
    return close_price.rolling(window).mean().iloc[-1]

def bollinger_band_width(close_price): # 布林通道，價格大部分時間應該待在通道裡
    ma20 = close_price.rolling(20).mean() 
    std20 = close_price.rolling(20).std() # 最近20天價格的標準差
    bb_upper = ma20 + 2 * std20
    bb_lower = ma20 - 2 * std20
    return (bb_upper - bb_lower) / ma20 * 100 # 4 * std20 / ma20 * 100

def price_to_bollinger_upper (close_price):
    ma20 = close_price.rolling(20).mean() 
    std20 = close_price.rolling(20).std()
    current_close = close_price.iloc[-1] # 取今日(就是最後一個)收盤價
    bb_upper = ma20 + 2 * std20

    return (current_close / bb_upper.iloc[-1] - 1) * 100

def record_add(records_db, Name, Id, close_price):

    ma5 = moving_average(close_price, 5)
    ma20 = moving_average(close_price, 20)
    ma60 = moving_average(close_price, 60)
    current_close = close_price.iloc[-1]

    # 特徵 1: 歷史波動率
    hist_vol = history_volatility(close_price)
    # 特徵 2: 布林通道寬度
    bb_width = bollinger_band_width(close_price)
    # 特徵 3: 股價距離 MA60 幾 %
    p_to_ma60 = (current_close / ma60 - 1) * 100
    # 特徵 4: 短均線 vs 長均線 強度
    trend_str = (ma5 / ma60 - 1) * 100
    # 特徵 5: 股價距離 MA20 幾 %
    p_to_ma20 = (current_close / ma20 - 1) * 100
    # 特徵 6: 股價距離布林通道上緣幾 %
    p_to_bbupper = price_to_bollinger_upper(close_price)
    # 特徵 7: 10 日價格變動率
    roc_10 = (current_close - close_price.iloc[-11]) / close_price.iloc[-11] * 100
    
    # 檢查 hist_vol 或 roc_10 是不是 NaN
    if np.isnan(hist_vol) or np.isnan(roc_10): return 

    records_db.append({
        'ID': Id,
        'Name': Name,
        'Close': current_close,
        'MA5': ma5,
        'F_Hist_Vol': hist_vol,
        'F_BB_Width': bb_width,
        'F_P_to_MA60': p_to_ma60,
        'F_Trend_Strength': trend_str,
        'F_P_to_MA20': p_to_ma20,
        'F_P_to_BBUpper': p_to_bbupper,
        'F_ROC_10': roc_10
    })

def top_20_extract(df):
    features = ['F_Hist_Vol', 'F_BB_Width', 'F_P_to_MA60', 'F_Trend_Strength', 'F_P_to_MA20', 'F_P_to_BBUpper', 'F_ROC_10']
    weights = [29.08, 19.33, 10.39, 7.67, 7.26, 5.09, 4.25]

    # 計算 PR 值 (0~1)，不直接排名 1、2、3...，是因為每天符合條件的股票數量不一樣，例如上下架
    for f in features:
        df[f + '_Rank'] = df[f].rank(pct=True)

    # 乘以權重
    df['AI_Score'] = 0.0
    for f, w in zip (features, weights): 
        df['AI_Score'] += df[f + '_Rank'] * w

    # 正規化為 100 分制
    max_score = sum(weights)
    df['AI_Score'] = (df['AI_Score'] / max_score) * 100

    # 當下收盤價必須站上 5MA
    df_filtered = df[df['Close'] >= df['MA5']].copy()
    top20 = df_filtered.sort_values(by='AI_Score', ascending=False).head(20)
    
    return top20

def top_20_dump(top20):
    
    print("\n" + "="*60)
    print("TOP 20 名單")
    print("="*60)
    print(f"{'排名':<4} | {'代號':<6} | {'股名':<10} | {'收盤價':<8} | {'AI 分數':<6}")
    print("-" * 60)

    for i, (_, row) in enumerate(top20.iterrows(), 1):
        name = row['Name']
        name_padded = name + chr(12288) * (5 - len(name)) if len(name) < 5 else name[:5]
        print(f"{i:<4} | {row['ID']:<6} | {name_padded} | {row['Close']:<8.2f} | {row['AI_Score']:>6.2f}")
        
    print("="*60)
    print("前 7 檔優先分配資金，跌破 MA5 第二天未站回無條件停損\n")

def top_20_save(top20):
    try:
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        csv_filename = os.path.join(desktop_path, f"Top20_{timestamp}.csv")
        columns_to_save = ['ID', 'Name', 'Close', 'AI_Score', 'F_Hist_Vol', 'F_BB_Width', 'F_P_to_MA60', 'F_Trend_Strength', 'F_P_to_MA20', 'F_P_to_BBUpper', 'F_ROC_10']
        top20[columns_to_save].to_csv(csv_filename, index=False, encoding='utf-8-sig')
        
        print(f"完整特徵明細已儲存至桌面：Top20_{timestamp}.csv")
    except:
        print("無法儲存 CSV 檔案至桌面，請確認權限。")

def main():
    stock_dict = get_tw_stock_list()
    print(f"取得標的共 {len(stock_dict)} 檔。")
    print("[2/3] 開始全市場掃描與數據下載...")
    
    all_tickers = list(stock_dict.keys()) # 把 stock_dict 裡所有的 key 取出來，轉成 list
    batch_size = 50
    records = []
    
    # 批次下載歷史資料
    # for i in range(0, len(all_tickers), batch_size): # e.g., range (0, 5, 2) 會回傳 0, 2, 4
    #     batch = all_tickers[i:i+batch_size]
    #     print(f"   下載進度: {min(i+batch_size, len(all_tickers))}/{len(all_tickers)}...", end='\r')
        
    #     try:
    #         # 抓取 100 天確保 60MA 計算正確
    #         data = yf.download(batch, period="100d", interval="1d", group_by='ticker', auto_adjust=False, progress=False, threads=True)
            
    #         for ticker in batch: # ticker = {code}{suffix}
    #             try:
    #                 df = data[ticker] if len(batch) > 1 else data
    #                 if df.empty or len(df) < 60: continue # 資料不到 60 天
    #                 df = df.dropna() # 把含有缺失值（NaN）的 row 刪掉
                    
    #                 close = df['Close'] # 確認收盤價至少有 60 筆
    #                 if len(close) < 60: continue
    #                 record_add(records, stock_dict[ticker]['name'], ticker.replace(".TW", "").replace(".TWO", ""), close)
    #             except: continue
    #     except: pass

    # print("\n資料下載完成！")
    # print("[3/3] 正在執行 AI 權重運算與全市場 PR 值排名...")
    
    # df_res = pd.DataFrame(records)
    # if df_res.empty:
    #     print("沒有足夠的資料可以運算。")
    #     return
    # top20 = top_20_extract(df_res)

    # top_20_dump(top20)
    # top_20_save(top20)

    # input("👉 程式執行完畢，請按 Enter 鍵關閉視窗...")

if __name__ == "__main__": # python code 的 entry point
    try:
        main()
    except Exception as e:
        print("\n" + "!"*60)
        print("程式執行中發生錯誤：")
        traceback.print_exc()
        print("!"*60)
        input("Enter 鍵關閉視窗...")