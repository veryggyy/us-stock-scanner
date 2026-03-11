import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股全市場掃描", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; }
    .tv-link { 
        display: inline-block; padding: 8px 16px; background-color: #2962FF; 
        color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 讀取本地 S&P 500 清單 ---
@st.cache_data
def get_local_sp500():
    file_path = 'sp500.csv'
    if os.path.exists(file_path):
        df = pd.read_csv(file_path)
        return dict(zip(df['Symbol'], df['Name'])), f"✅ 已從本地 CSV 載入 {len(df)} 檔標的"
    else:
        return {"AAPL":"Apple","NVDA":"NVIDIA","AVGO":"Broadcom"}, "⚠️ 找不到 CSV，使用預設標的"

# --- 3. 分析引擎 ---
def analyze_stock(df, threshold):
    try:
        if df is None or len(df) < 40: return None
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA20_Slope'] = df['MA20'].diff(2)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        ret = (curr['Close'] / prev['Close'] - 1) * 100
        
        # 條件：價格 > MA20 且 MA20 上揚 且 K > D
        if curr['Close'] > curr['MA20'] and curr['MA20_Slope'] > 0 and curr['K'] > curr['D'] and ret >= threshold:
            return {
                "現價": round(float(curr['Close']), 2), "漲幅": round(ret, 2),
                "K值": int(curr['K']), "支撐": round(float(curr['Close'] - (df['ATR'].iloc[-1] * 1.5)), 2),
                "評分": ret + (curr['K'] / 10)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("🇺🇸 2026 美股全市場強勢波段掃描")
with st.sidebar:
    ret_target = st.slider("漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描檔數", 10, 500, 100)
    if st.button("🔄 重置快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始全市場掃描", use_container_width=True):
    all_stocks, msg = get_local_sp500()
    st.info(msg)
    
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    data = yf.download(tickers, period="6mo", group_by='ticker', auto_adjust=True, progress=False)
    
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
        st.success(f"✅ 找到 {len(results)} 檔符合條件標的")
        for item in results:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.subheader(f"{item['代碼']} - {item['名稱']}")
                c2.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                c3.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 查看即時線圖</a>', unsafe_allow_html=True)
                st.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐']}`")
    else:
        st.warning("目前無符合標的。")
