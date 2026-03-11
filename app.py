import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import urllib3
from datetime import datetime

# 隱藏 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 S&P 500 強勢掃描", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; font-weight: 800; }
    .price-card { padding: 15px; background: #0f172a; border-radius: 12px; border: 1px solid #475569; margin-bottom: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 自動抓取 S&P 500 清單 ---
@st.cache_data(ttl=86400) # 每天更新一次清單即可
def get_sp500_tickers():
    try:
        # 從 Wikipedia 抓取 S&P 500 列表
        url = 'https://en.wikipedia.org'
        table = pd.read_html(url)
        df = table[0]
        # 處理部分代號含點的情況 (如 BRK.B 改為 BRK-B 以符合 yfinance)
        tickers = df['Symbol'].str.replace('.', '-', regex=False).tolist()
        names = df['Security'].tolist()
        return dict(zip(tickers, names)), "✅ 已成功獲取 S&P 500 最新成分股"
    except Exception as e:
        return {"AAPL": "Apple", "NVDA": "NVIDIA", "TSLA": "Tesla"}, f"⚠️ 抓取失敗: {e}，使用預設標的"

# --- 3. 分析引擎 ---
def analyze_stock(df, threshold):
    try:
        if df is None or len(df) < 65: return None
        
        # 指標計算
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
        
        # 強勢邏輯：MA 多頭排列 + MA20 上揚 + KD 金叉 + 帶量突破
        is_bullish = (curr['Close'] > curr['MA20'] > curr['MA60']) and (curr['MA20_Slope'] > 0)
        is_kd_cross = (curr['K'] > curr['D']) and (prev['K'] <= prev['D'])
        is_breakout = (vol_ratio > 1.2) and (ret >= threshold)
        
        if is_bullish and is_kd_cross and is_breakout:
            atr_val = df['ATR'].iloc[-1]
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "量能比": round(vol_ratio, 2),
                "參考支撐": round(float(curr['Close'] - (atr_val * 2)), 2),
                "波段目標": round(float(curr['Close'] + (atr_val * 3.5)), 2),
                "評分": ret + (vol_ratio * 1.5)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("⚡ 2026 S&P 500 強勢波段掃描器")
st.caption(f"📅 數據時間: {datetime.now().strftime('%Y-%m-%d')} | 策略：多頭排列 + 帶量金叉")

with st.sidebar:
    st.header("⚙️ 參數設定")
    ret_target = st.slider("突破漲幅門檻 (%)", 0.0, 5.0, 1.5, 0.5)
    scan_limit = st.slider("掃描檔數", 50, 500, 100)
    if st.button("🔄 重置數據"):
        st.cache_data.clear()
        st.rerun()

# --- 5. 執行 ---
if st.button("🚀 開始掃描標普 500 強勢股", use_container_width=True):
    all_stocks, msg = get_sp500_tickers()
    st.info(msg)
    
    # 限制掃描數量以維持效能
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 批次下載數據
    data = yf.download(tickers, period="8mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for i, sym in enumerate(tickers):
        status_text.text(f"正在分析: {sym}...")
        try:
            df = data[sym].dropna()
            res = analyze_stock(df, ret_target)
            if res:
                res["股票代碼"] = sym
                res["名稱"] = all_stocks[sym]
                results.append(res)
        except: continue
        progress_bar.progress((i + 1) / len(tickers))
    
    status_text.empty()
    progress_bar.empty()

    if results:
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        st.success(f"✅ 找到 {len(results)} 檔符合條件標的")
        
        # 用 Grid 方式呈現
        cols = st.columns(2)
        for idx, item in enumerate(results):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.subheader(f"{item['股票代碼']} - {item['名稱']}")
                    c1, c2 = st.columns(2)
                    c1.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                    c2.write(f"📊 量能比: `{item['量能比']}x`")
                    st.markdown(f"""
                    <div class="price-card">
                    🔵 參考支撐：<span style="color:#4FACFE;">${item['參考支撐']}</span><br>
                    🔴 波段目標：<span style="color:#FF4B4B;">${item['波段目標']}</span>
                    </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("❌ 目前市場條件下，選定檔數內無符合標的。請嘗試調低漲幅門檻或增加掃描檔數。")

st.divider()
st.caption("⚠ 免責聲明：此程式僅供技術分析參考，不構成投資建議。美股波動大，請務必設置止損。")
