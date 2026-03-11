import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股 S&P 500 強勢掃描器", layout="wide")

# --- 2. 穩定版 S&P 500 清單 (直接內建代號，不再抓取網頁) ---
@st.cache_data
def get_sp500_static():
    # 這裡預置了 S&P 500 最核心的 100+ 檔標的，確保穩定性
    stocks = {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "NVDA": "NVIDIA",
        "META": "Meta", "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
        "AMD": "AMD", "PLTR": "Palantir", "ORCL": "Oracle", "CRM": "Salesforce", "V": "Visa",
        "MA": "Mastercard", "JPM": "JPMorgan", "UNH": "UnitedHealth", "WMT": "Walmart", "LLY": "Eli Lilly",
        "ABV": "AbbVie", "ACN": "Accenture", "ADBE": "Adobe", "AMD": "AMD", "AXP": "Amex",
        "BAC": "BofA", "CAT": "Caterpillar", "DIS": "Disney", "GS": "Goldman Sachs", "INTC": "Intel",
        "KO": "Coca-Cola", "LIN": "Linde", "LOW": "Lowe's", "MCD": "McDonald's", "NKE": "Nike",
        "PFE": "Pfizer", "PG": "P&G", "QCOM": "Qualcomm", "RTX": "Raytheon", "SBUX": "Starbucks",
        "TMO": "Thermo Fisher", "TXN": "TI", "UPS": "UPS", "VZ": "Verizon", "XOM": "Exxon"
    }
    return stocks

# --- 3. 分析引擎 ---
def analyze_stock(df, threshold):
    try:
        if df is None or len(df) < 65: return None
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
        
        # 強勢邏輯
        is_bullish = (curr['Close'] > curr['MA20'] > curr['MA60']) and (curr['MA20_Slope'] > 0)
        is_kd_cross = (curr['K'] > curr['D']) and (prev['K'] <= prev['D'])
        
        if is_bullish and is_kd_cross and (ret >= threshold):
            atr_val = df['ATR'].iloc[-1]
            return {
                "現價": round(float(curr['Close']), 2), "漲幅": round(ret, 2), "量能比": round(vol_ratio, 2),
                "參考支撐": round(float(curr['Close'] - (atr_val * 1.5)), 2),
                "波段目標": round(float(curr['Close'] + (atr_val * 3.0)), 2),
                "評分": ret + (vol_ratio * 1.5)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("🇺🇸 2026 美股強勢波段掃描器 (穩定版)")
with st.sidebar:
    ret_target = st.slider("突破漲幅門檻 (%)", 0.0, 5.0, 0.5, 0.1) # 建議設低一點，例如 0.5%
    scan_limit = st.slider("掃描數量", 10, 100, 50)
    if st.button("🔄 重置快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始掃描", use_container_width=True):
    all_stocks = get_sp500_static()
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    data = yf.download(tickers, period="8mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for i, sym in enumerate(tickers):
        try:
            df = data[sym].dropna() if len(tickers) > 1 else data.dropna()
            res = analyze_stock(df, ret_target)
            if res:
                res["代碼"], res["名稱"] = sym, all_stocks[sym]
                results.append(res)
        except: continue
        progress_bar.progress((i + 1) / len(tickers))
    
    if results:
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        cols = st.columns(2)
        for idx, item in enumerate(results):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.subheader(f"{item['代碼']} - {item['名稱']}")
                    st.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                    st.write(f"🟢 支撐: ${item['參考支撐']} | 🔴 目標: ${item['波段目標']}")
    else:
        st.warning("❌ 門檻內無符合標的。請試著將「突破漲幅門檻」調低至 0.1% 或 0%。")
