import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股強勢波段掃描器", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; font-weight: 800; }
    .price-card { padding: 15px; background: #0f172a; border-radius: 12px; border: 1px solid #475569; margin-bottom: 10px; line-height: 1.8; }
    .tv-link { color: #3b82f6; text-decoration: none; font-weight: bold; border: 1px solid #3b82f6; padding: 2px 8px; border-radius: 4px; }
    .tv-link:hover { background-color: #3b82f6; color: white; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 穩定版 S&P 500 權值股清單 (避免網頁抓取失敗) ---
@st.cache_data
def get_us_stocks():
    return {
        "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "NVDA": "NVIDIA",
        "META": "Meta", "TSLA": "Tesla", "AVGO": "Broadcom", "COST": "Costco", "NFLX": "Netflix",
        "AMD": "AMD", "PLTR": "Palantir", "ORCL": "Oracle", "CRM": "Salesforce", "V": "Visa",
        "MA": "Mastercard", "JPM": "JPMorgan", "UNH": "UnitedHealth", "WMT": "Walmart", "LLY": "Eli Lilly",
        "ABBV": "AbbVie", "ACN": "Accenture", "ADBE": "Adobe", "AXP": "Amex", "BAC": "BofA",
        "CAT": "Caterpillar", "DIS": "Disney", "GS": "Goldman Sachs", "INTC": "Intel", "KO": "Coca-Cola",
        "MCD": "McDonald's", "PFE": "Pfizer", "PG": "P&G", "QCOM": "Qualcomm", "SBUX": "Starbucks",
        "TMO": "Thermo Fisher", "TXN": "TI", "UPS": "UPS", "VZ": "Verizon", "XOM": "Exxon",
        "IBM": "IBM", "DE": "Deere", "NKE": "Nike", "HON": "Honeywell", "GE": "GE Aerospace",
        "AMT": "American Tower", "MDLZ": "Mondelez", "ISRG": "Intuitive Surg", "LRCX": "Lam Research"
    }

# --- 3. 分析引擎 (優化版：MA20/60 多頭排列 + KD 強勢) ---
def analyze_stock_v2(df, threshold):
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
        
        # 篩選邏輯：
        # 1. 站上月線且月線向上
        # 2. KD 多頭 (K > D) 且不在超買區 (K < 85)
        # 3. 符合漲幅門檻
        is_ma_ok = (curr['Close'] > curr['MA20']) and (curr['MA20_Slope'] > 0)
        is_kd_ok = (curr['K'] > curr['D']) and (curr['K'] < 85)
        
        if is_ma_ok and is_kd_ok and (ret >= threshold):
            atr_val = df['ATR'].iloc[-1]
            # 綜合評分系統：漲幅 + 量比 + K值權重
            score = ret + (vol_ratio * 1.5) + (curr['MA20_Slope'] * 2)
            
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "量能比": round(vol_ratio, 2),
                "K值": int(curr['K']),
                "支撐": round(float(curr['Close'] - (atr_val * 1.5)), 2),
                "評分": score
            }
    except: return None
    return None

# --- 4. 主介面 ---
st.title("⚡ 2026 美股強勢波段掃描器")
st.caption(f"📅 系統日期: {datetime.now().strftime('%Y-%m-%d')} | 策略：月線趨勢向上 + KD 多頭")

with st.sidebar:
    st.header("⚙️ 篩選參數")
    ret_target = st.slider("漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描檔數 (S&P 500 核心)", 10, 50, 30)
    if st.button("🔄 重置數據"):
        st.cache_data.clear()
        st.rerun()

# --- 5. 執行掃描 ---
if st.button("🚀 開始多頭掃描 (排序由強至弱)", use_container_width=True):
    all_stocks = get_us_stocks()
    tickers = list(all_stocks.keys())[:scan_limit]
    results = []
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    # 批次下載
    data = yf.download(tickers, period="8mo", group_by='ticker', auto_adjust=True, progress=False)
    
    for i, sym in enumerate(tickers):
        status_text.text(f"正在分析: {sym}...")
        try:
            df = data[sym].dropna() if len(tickers) > 1 else data.dropna()
            res = analyze_stock_v2(df, ret_target)
            if res:
                res["代碼"] = sym
                res["名稱"] = all_stocks[sym]
                results.append(res)
        except: continue
        progress_bar.progress((i + 1) / len(tickers))
    
    status_text.empty()
    progress_bar.empty()

    if results:
        # 按評分排序
        results = sorted(results, key=lambda x: x['評分'], reverse=True)
        st.success(f"✅ 找到 {len(results)} 檔符合條件標的")
        
        for item in results:
            with st.container(border=True):
                # 佈局：代號與 TradingView 連結
                c_title, c_link = st.columns([4, 1])
                c_title.subheader(f"{item['代碼']} - {item['名稱']}")
                c_link.markdown(f'<a href="https://www.tradingview.com{item["代碼"]}/" target="_blank" class="tv-link">🔗 查看線圖</a>', unsafe_allow_html=True)
                
                # 數據顯示
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("價格", f"${item['現價']}", f"{item['漲幅']}%")
                m2.write(f"📊 量能比: `{item['量能比']}x`")
                m3.write(f"📈 K值: `{item['K值']}`")
                m4.write(f"🛡️ 支撐: `${item['支撐']}`")
                
                # 進度條模擬強弱度
                st.progress(min(max((item['評分'] + 2) / 10, 0.0), 1.0))
    else:
        st.error("❌ 目前市場環境較弱，無符合條件標的。請調低漲幅門檻或重置數據。")

st.divider()
st.caption("⚠ 免責聲明：本工具僅供參考，美股無漲跌幅限制，請務必搭配大盤與止損操作。")
