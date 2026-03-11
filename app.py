import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 US Stock Scanner", layout="centered")

# --- 2. 獲取美股清單 (範例：Nasdaq 100 與熱門股) ---
@st.cache_data(ttl=3600)
def get_us_stock_list():
    # 這裡可以自行增加更多代號，例如 AAPL, TSLA, NVDA 等
    stocks = {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon",
        "NVDA": "NVIDIA", "TSLA": "Tesla", "META": "Meta", "AVGO": "Broadcom",
        "COST": "Costco", "NFLX": "Netflix", "AMD": "AMD", "PLTR": "Palantir"
    }
    return stocks, f"✅ 已載入觀察清單 (共 {len(stocks)} 檔)"

# --- 3. 核心 SOP 分析引擎 ---
def analyze_sop_us(df, up_threshold):
    try:
        if df is None or len(df) < 65: return None
        # yfinance 美股資料欄位處理
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].apply(pd.to_numeric).dropna()
        
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA60'] = ta.sma(df['Close'], length=60)
        df['MA20_Slope'] = df['MA20'].diff(3) 
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        df['VMA5'] = ta.sma(df['Volume'], length=5)
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        ret = (curr['Close'] / prev['Close'] - 1) * 100
        vol_ratio = curr['Volume'] / curr['VMA5']
        
        # 多頭排列邏輯
        is_bull = (curr['Close'] > curr['MA20'] > curr['MA60']) and (curr['MA20_Slope'] > 0)
        is_kd_cross = (curr['K'] > curr['D']) and (prev['K'] <= prev['D'])
        is_breakout = (vol_ratio > 1.2) and (ret >= up_threshold)
        
        if is_bull and is_kd_cross and is_breakout:
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "量能比": round(vol_ratio, 2),
                "買進": round(float(curr['Close']), 2),
                "目標": round(float(curr['Close'] + (df['ATR'].iloc[-1] * 3)), 2),
                "評分": ret + (vol_ratio * 2)
            }
    except: return None
    return None

# --- 4. 介面 ---
st.title("🇺🇸 2026 美股強勢波段掃描")
with st.sidebar:
    ret_target = st.slider("漲幅門檻 (%)", 0.0, 10.0, 2.0, 0.5)
    if st.button("🔄 清除快取"): st.cache_data.clear(); st.rerun()

if st.button("🔵 開始美股掃描", use_container_width=True):
    all_stocks, msg = get_us_stock_list()
    st.info(msg)
    
    tickers = list(all_stocks.keys())
    results = []
    
    # 批次下載美股數據
    data = yf.download(tickers, period="8mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for sym in tickers:
        res = analyze_sop_us(data[sym].dropna(), ret_target)
        if res:
            res["股票"] = f"{sym} ({all_stocks[sym]})"
            results.append(res)
    
    if results:
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        for item in results:
            with st.container(border=True):
                st.subheader(item['股票'])
                st.metric("Price", f"${item['現價']}", f"{item['漲幅']}%")
                st.write(f"🎯 目標價: `${item['目標']}` | 📊 量比: `{item['量能比']}x` ")
    else:
        st.warning("目前無符合標的，建議調低漲幅門檻。")
