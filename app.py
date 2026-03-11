import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
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
        color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.9rem;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. 讀取本地 S&P 500 清單 (相容多欄位格式) ---
@st.cache_data
def get_local_sp500():
    file_path = 'sp500.csv'
    if os.path.exists(file_path):
        try:
            # 自動讀取 CSV 並抓取前兩欄 (Symbol 與 Security/Name)
            df = pd.read_csv(file_path)
            # 處理代號中的點 (如 BRK.B 改為 BRK-B)
            tickers = df.iloc[:, 0].astype(str).str.replace('.', '-', regex=False).tolist()
            names = df.iloc[:, 1].tolist()
            return dict(zip(tickers, names)), f"✅ 已成功載入 {len(df)} 檔 S&P 500 標的"
        except Exception as e:
            return {"AAPL":"Apple","NVDA":"NVIDIA"}, f"⚠️ CSV 讀取失敗: {e}"
    else:
        return {"AAPL":"Apple","MSFT":"Microsoft","NVDA":"NVIDIA","AVGO":"Broadcom"}, "⚠️ 找不到 sp500.csv，目前使用保底清單"

# --- 3. 核心分析引擎 (含 MA200 長線濾網) ---
def analyze_stock(df, threshold):
    try:
        # 確保有足夠數據計算 MA200
        if df is None or len(df) < 200: return None
        
        # 指標計算
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['MA20_Slope'] = df['MA20'].diff(3)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        ret = (curr['Close'] / prev['Close'] - 1) * 100
        
        # 篩選邏輯：
        # 1. 站上月線(MA20) 且 月線趨勢向上
        # 2. 站上年線(MA200) -> 長線保護短線
        # 3. KD 多頭 (K > D) 且 K 值低於 85 (避免過熱)
        is_bullish = (curr['Close'] > curr['MA20']) and (curr['MA20_Slope'] > 0)
        is_long_trend = (curr['Close'] > curr['MA200'])
        is_kd_ok = (curr['K'] > curr['D']) and (curr['K'] < 85)
        
        if is_bullish and is_long_trend and is_kd_ok and (ret >= threshold):
            atr_val = df['ATR'].iloc[-1]
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "K值": int(curr['K']),
                "支撐參考": round(float(curr['Close'] - (atr_val * 2)), 2),
                "目標參考": round(float(curr['Close'] + (atr_val * 3.5)), 2),
                "評分": ret + (curr['K'] / 10)
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("🚀 2026 美股全市場強勢波段掃描")
st.caption(f"📅 數據日期: {datetime.now().strftime('%Y-%m-%d')} | 策略：MA20/200 多頭排列 + KD 多頭")

with st.sidebar:
    st.header("⚙️ 篩選設定")
    ret_target = st.slider("突破漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描檔數 (依 CSV 順序)", 10, 505, 100)
    if st.button("🔄 重置快取數據"):
        st.cache_data.clear()
        st.rerun()

# --- 5. 執行執行 ---
if st.button("🔍 開始全市場掃描 (排序由強至弱)", use_container_width=True):
    all_stocks, status_msg = get_local_sp500()
    st.info(status_msg)
    
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 批次下載數據 (8個月數據以確保 MA200 計算)
    data = yf.download(tickers, period="10mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for i, sym in enumerate(tickers):
        status_text.text(f"正在分析: {sym}...")
        try:
            df = data[sym].dropna() if len(tickers) > 1 else data.dropna()
            res = analyze_stock(df, ret_target)
            if res:
                res["代碼"], res["名稱"] = sym, all_stocks[sym]
                results.append(res)
        except: continue
        progress_bar.progress((i + 1) / len(tickers))
    
    status_text.empty()
    progress_bar.empty()

    if results:
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        st.success(f"🎯 找到 {len(results)} 檔符合「長短線多頭」標的")
        
        # 下載按鈕
        res_df = pd.DataFrame(results)[["代碼", "名稱", "現價", "漲幅", "K值", "支撐參考"]]
        st.download_button("📥 下載強勢股清單 (CSV)", res_df.to_csv(index=False).encode('utf-8-sig'), "strong_stocks.csv", "text/csv")
        
        # 顯示結果
        for item in results:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.subheader(f"{item['代碼']} - {item['名稱']}")
                    st.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐參考']}` | 🎯 目標: `${item['目標參考']}`")
                with c2:
                    st.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                with c3:
                    st.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 查看即時線圖</a>', unsafe_allow_html=True)
    else:
        st.error("❌ 目前市場環境內無符合「多頭起漲」標的。建議調低漲幅門檻或增加掃描檔數。")

st.divider()
st.caption("⚠ 免責聲明：此工具僅供技術分析參考。美股波動性高，請務必設置止損位並配合市場大盤環境。")
