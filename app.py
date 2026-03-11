import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股強勢掃描器", layout="wide")

# --- 2. 擴展版穩定清單 ---
@st.cache_data
def get_us_stocks():
    return {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "NVDA": "NVIDIA",
        "META": "Meta", "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
        "AMD": "AMD", "PLTR": "Palantir", "ORCL": "Oracle", "CRM": "Salesforce", "V": "Visa",
        "MA": "Mastercard", "JPM": "JPMorgan", "UNH": "UnitedHealth", "WMT": "Walmart", "LLY": "Eli Lilly",
        "ABBV": "AbbVie", "ACN": "Accenture", "ADBE": "Adobe", "AXP": "Amex", "BAC": "BofA",
        "CAT": "Caterpillar", "DIS": "Disney", "GS": "Goldman Sachs", "INTC": "Intel", "KO": "Coca-Cola"
    }

# --- 3. 分析引擎 (邏輯放寬版) ---
def analyze_stock_relaxed(df, threshold):
    try:
        if df is None or len(df) < 30: return None
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA20_Slope'] = df['MA20'].diff(2)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        ret = (curr['Close'] / prev['Close'] - 1) * 100
        
        # --- 寬鬆版邏輯 ---
        is_above_ma20 = curr['Close'] > curr['MA20']  # 站上月線
        is_ma20_up = curr['MA20_Slope'] > 0          # 月線趨勢向上
        is_k_up = curr['K'] > curr['D']               # KD 多頭
        
        if is_above_ma20 and is_ma20_up and is_k_up and (ret >= threshold):
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "K值": int(curr['K']),
                "支撐": round(float(curr['Close'] - (df['ATR'].iloc[-1] * 1.5)), 2),
                "評分": ret + (curr['K'] / 10)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("🇺🇸 2026 美股強勢波段掃描器 (優化版)")
with st.sidebar:
    ret_target = st.slider("漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1) # 允許搜尋今日微跌但趨勢仍強的股票
    scan_limit = st.slider("掃描數量", 10, 30, 20)
    if st.button("🔄 重置快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始掃描", use_container_width=True):
    all_stocks = get_us_stocks()
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    data = yf.download(tickers, period="6mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for i, sym in enumerate(tickers):
        try:
            df = data[sym].dropna() if len(tickers) > 1 else data.dropna()
            res = analyze_stock_relaxed(df, ret_target)
            if res:
                res["代碼"], res["名稱"] = sym, all_stocks[sym]
                results.append(res)
        except: continue
        progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        st.success(f"✅ 找到 {len(results)} 檔趨勢偏多標的")
        for item in results:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1, 1, 2])
                c1.subheader(item['代碼'])
                c2.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                c3.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐']}`")
    else:
        st.warning("目前市場環境極度疲弱，建議將漲幅門檻調至 -0.5% 觀察抗跌標的。")
