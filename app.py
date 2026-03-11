import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股強勢波段掃描系統", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; font-weight: 800; }
    .price-card { padding: 15px; background: #0f172a; border-radius: 12px; border: 1px solid #475569; margin-bottom: 10px; }
    .tv-link { 
        display: inline-block; padding: 5px 12px; background-color: #2962FF; 
        color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.85rem;
    }
    .news-link { color: #94a3b8; font-size: 0.8rem; text-decoration: underline; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 讀取本地 S&P 500 清單 (相容多欄位格式) ---
@st.cache_data
def get_full_sp500_data():
    file_path = 'sp500.csv'
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            # 處理代號中的點
            df['Symbol'] = df.iloc[:, 0].astype(str).str.replace('.', '-', regex=False)
            # 確保有產業欄位，如果沒有則預設為 "General"
            if 'GICS Sector' not in df.columns:
                df['GICS Sector'] = 'All Sectors'
            return df
        except: return None
    return None

# --- 3. 大盤環境檢查 (SPY) ---
def get_market_regime():
    try:
        spy = yf.download("SPY", period="6mo", progress=False)
        spy['MA20'] = ta.sma(spy['Close'], length=20)
        curr = spy.iloc[-1]
        if curr['Close'] > curr['MA20']:
            return "🟢 大盤位於月線上 (適合積極操作)", "#00FFCC"
        else:
            return "🔴 大盤位於月線下 (建議保守、減碼)", "#FF4B4B"
    except: return "⚠️ 無法取得大盤數據", "#FFFFFF"

# --- 4. 核心分析引擎 ---
def analyze_stock(df, threshold):
    try:
        if df is None or len(df) < 200: return None
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['MA20_Slope'] = df['MA20'].diff(3)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        curr = df.iloc[-1]
        ret = (curr['Close'] / df.iloc[-2]['Close'] - 1) * 100
        
        # 篩選邏輯：站上月線且向上 + 站上年線 + KD 多頭
        is_ma_ok = curr['Close'] > curr['MA20'] and curr['MA20_Slope'] > 0
        is_long_ok = curr['Close'] > curr['MA200']
        is_kd_ok = curr['K'] > curr['D'] and curr['K'] < 85
        
        if is_ma_ok and is_long_ok and is_kd_ok and ret >= threshold:
            atr_val = df['ATR'].iloc[-1]
            return {
                "現價": round(float(curr['Close']), 2), "漲幅": round(ret, 2), "K值": int(curr['K']),
                "支撐": round(float(curr['Close'] - (atr_val * 2)), 2), "目標": round(float(curr['Close'] + (atr_val * 3.5)), 2),
                "評分": ret + (curr['K'] / 10)
            }
    except: return None
    return None

# --- 5. 主介面佈局 ---
st.title("🏹 2026 美股全市場強勢波段雷達")
market_msg, market_color = get_market_regime()
st.markdown(f"**市場環境：<span style='color:{market_color};'>{market_msg}</span>**", unsafe_allow_html=True)

df_sp500 = get_full_sp500_data()

with st.sidebar:
    st.header("⚙️ 篩選參數")
    if df_sp500 is not None:
        sectors = ["全部產業"] + sorted(df_sp500['GICS Sector'].unique().tolist())
        selected_sector = st.selectbox("選擇產業別", sectors)
    
    ret_target = st.slider("突破漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描數量", 10, 505, 150)
    
    if st.button("🔄 重置快取"):
        st.cache_data.clear()
        st.rerun()

# --- 6. 執行掃描 ---
if st.button("🚀 開始產業別多頭掃描", use_container_width=True):
    if df_sp500 is not None:
        # 產業篩選
        if selected_sector != "全部產業":
            target_df = df_sp500[df_sp500['GICS Sector'] == selected_sector]
        else:
            target_df = df_sp500
            
        tickers_dict = dict(zip(target_df.iloc[:, 0], target_df.iloc[:, 1]))
        tickers = list(tickers_dict.keys())[:scan_limit]
        
        st.info(f"正在掃描 {selected_sector} 中的 {len(tickers)} 檔標的...")
        results = []
        progress_bar = st.progress(0)
        
        # 批次下載
        data = yf.download(tickers, period="10mo", group_by='ticker', auto_adjust=True, progress=False)
        
        for i, sym in enumerate(tickers):
            try:
                df_stock = data[sym].dropna() if len(tickers) > 1 else data.dropna()
                res = analyze_stock(df_stock, ret_target)
                if res:
                    res["代碼"], res["名稱"] = sym, tickers_dict[sym]
                    results.append(res)
            except: continue
            progress_bar.progress((i + 1) / len(tickers))
            
        if results:
            results = sorted(results, key=lambda x: x['評分'], reverse=True)
            st.success(f"🎯 找到 {len(results)} 檔多頭共振標的")
            
            # 下載按鈕
            csv_data = pd.DataFrame(results).to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 匯出清單 (CSV)", csv_data, "strong_stocks.csv", "text/csv")
            
            # 顯示結果
            for item in results:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.subheader(f"{item['代碼']} - {item['名稱']}")
                        st.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐']}` | 🎯 目標: `${item['目標']}`")
                        st.markdown(f"[📰 Yahoo 新聞](https://finance.yahoo.com{item['代碼']}/news)", unsafe_allow_html=True)
                    with c2:
                        st.metric("現價", f"${item['現價']}", f"{item['漲幅']}%")
                    with c3:
                        st.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 互動線圖</a>', unsafe_allow_html=True)
        else:
            st.error("目前環境下無符合條件標的。")
    else:
        st.error("找不到 sp500.csv，請確認檔案已上傳。")

st.caption("⚠ 免責聲明：此程式僅供參考，不代表投資建議。投資美股請務必設置止損點。")
