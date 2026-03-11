import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股全市場強勢掃描", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; font-weight: 800; }
    .price-card { padding: 15px; background: #0f172a; border-radius: 12px; border: 1px solid #475569; margin-bottom: 10px; line-height: 1.8; }
    .tv-link { 
        display: inline-block; padding: 5px 12px; background-color: #2962FF; 
        color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 自動獲取 S&P 500 全清單 (使用更穩定的來源) ---
@st.cache_data(ttl=86400)
def get_sp500_full_list():
    try:
        # 使用資料源直接抓取，避免被維基百科 403 阻擋
        url = 'https://datahub.io'
        df = pd.read_csv(url)
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        names = df['Name'].tolist()
        return dict(zip(tickers, names)), f"✅ 已成功載入 S&P 500 全成分股 (共 {len(tickers)} 檔)"
    except:
        # 如果網路失敗，保底 30 檔
        backup = {"AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","GOOGL":"Alphabet","AMZN":"Amazon","META":"Meta","TSLA":"Tesla","AVGO":"Broadcom"}
        return backup, "⚠️ 網路受限，目前使用核心權值股模式"

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
        
        # 核心邏輯：價格在月線上 + 月線趨勢向上 + K > D
        if curr['Close'] > curr['MA20'] and curr['MA20_Slope'] > 0 and curr['K'] > curr['D'] and ret >= threshold:
            return {
                "現價": round(float(curr['Close']), 2), "漲幅": round(ret, 2),
                "K值": int(curr['K']), "支撐": round(float(curr['Close'] - (df['ATR'].iloc[-1] * 1.5)), 2),
                "評分": ret + (curr['K'] / 10)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("⚡ 2026 美股全市場強勢波段掃描")
with st.sidebar:
    st.header("⚙️ 篩選參數")
    ret_target = st.slider("突破漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描檔數 (由市值排名前開始)", 50, 500, 150)
    if st.button("🔄 重置數據快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始全市場掃描 (排序由強至弱)", use_container_width=True):
    all_stocks, msg = get_sp500_full_list()
    st.info(msg)
    
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    # 批次下載數據
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
                c1, c2, c3 = st.columns([2, 2, 1])
                c1.subheader(f"{item['代碼']} - {item['名稱']}")
                c2.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                # 修復後的 TradingView 連結
                c3.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 看線圖</a>', unsafe_allow_html=True)
                st.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐']}`")
    else:
        st.warning("❌ 目前範圍內無符合標的。請調低漲幅門檻或增加掃描檔數。")
