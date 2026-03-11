import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股帶量強勢雷達", layout="wide")

st.markdown("""
    <style>
    .stMetric { background-color: #1e293b; padding: 15px; border-radius: 10px; border: 1px solid #334155; }
    [data-testid="stMetricValue"] { color: #00FFCC !important; font-weight: 800; }
    .price-card { padding: 15px; background: #0f172a; border-radius: 12px; border: 1px solid #475569; margin-bottom: 10px; }
    .tv-link { 
        display: inline-block; padding: 6px 14px; background-color: #2962FF; 
        color: white !important; text-decoration: none; border-radius: 5px; font-weight: bold; font-size: 0.85rem;
    }
    .vol-badge { background-color: #f59e0b; color: #000; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8rem; }
    .sector-badge { background-color: #4b5563; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.8rem; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 中文名稱與產業對照表 ---
CN_NAME_MAP = {
    "AAPL": "蘋果", "MSFT": "微軟", "NVDA": "輝達", "GOOGL": "Google", "AMZN": "亞馬遜",
    "META": "臉書", "TSLA": "特斯拉", "AVGO": "博通", "COST": "好市多", "NFLX": "網飛",
    "AMD": "超微", "ORCL": "甲骨文", "CRM": "賽富時", "PLTR": "帕蘭泰爾", "MPC": "馬拉松石油",
    "SPY": "標普500 ETF", "QQQ": "納斯達克100 ETF", "SOXL": "半導體3倍做多", "TQQQ": "納指3倍做多",
    "SMH": "半導體 ETF", "V": "威士卡", "MA": "萬事達卡", "UNH": "聯合健康", "LLY": "禮來",
    "WMT": "沃爾瑪", "JPM": "摩根大通", "XOM": "埃克森美孚", "CVX": "雪佛龍", "KO": "可口可樂"
}

SECTOR_MAP = {
    "Information Technology": "資訊科技", "Health Care": "醫療保健", "Financials": "金融業",
    "Consumer Discretionary": "非核心消費", "Communication Services": "通訊服務", "Industrials": "工業",
    "Consumer Staples": "核心消費", "Energy": "能源", "Utilities": "公用事業", "Real Estate": "房地產",
    "Materials": "原物料", "ETF - 大盤指數": "ETF - 大盤指數", "ETF - 產業型": "ETF - 產業型",
    "ETF - 槓桿型": "ETF - 槓桿/反向型", "ETF - 股息價值": "ETF - 股息/價值型", "All Sectors": "全部產業"
}

# --- 3. 數據載入 ---
@st.cache_data
def get_full_data():
    file_path = 'sp500.csv'
    if os.path.exists(file_path):
        try:
            df = pd.read_csv(file_path)
            df['Symbol'] = df.iloc[:, 0].astype(str).str.replace('.', '-', regex=False)
            if 'GICS Sector' not in df.columns:
                df['GICS Sector'] = 'All Sectors'
            df['Sector_CN'] = df['GICS Sector'].map(lambda x: SECTOR_MAP.get(x, x))
            return df
        except: return None
    return None

# --- 4. 大盤環境檢查 ---
def get_market_regime():
    try:
        spy = yf.Ticker("SPY").history(period="6mo")
        if spy.empty: return "⚠️ 無法取得大盤數據", "#FFFFFF", 0
        spy['MA20'] = ta.sma(spy['Close'], length=20)
        curr, ma20 = spy['Close'].iloc[-1], spy['MA20'].iloc[-1]
        spy_ret = (spy['Close'].iloc[-1] / spy['Close'].iloc[-2] - 1) * 100
        if curr > ma20:
            return "🟢 大盤位於月線上 (多頭有利)", "#00FFCC", spy_ret
        else:
            return "🔴 大盤位於月線下 (空頭防禦)", "#FF4B4B", spy_ret
    except: return "⚠️ 數據超載", "#FFFFFF", 0

# --- 5. 核心分析引擎 (抗跌強勢分析版) ---
def analyze_stock_full(df, threshold, spy_ret):
    try:
        if df is None or len(df) < 60: return None
        df.columns = [str(c).capitalize() for c in df.columns]
        
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA20_Slope'] = df['MA20'].diff(3)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        df['VMA5'] = ta.sma(df['Volume'], length=5)
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        ret = (float(curr['Close']) / float(prev['Close']) - 1) * 100
        vol_ratio = round(float(curr['Volume'] / curr['VMA5']), 2)
        
        # 即使不符合多頭條件，也回傳數據用於產業分析
        stock_data = {
            "漲幅": ret, "量能比": vol_ratio, "現價": round(float(curr['Close']), 2),
            "K值": int(curr['K']), "相對大盤": round(ret - spy_ret, 2)
        }

        # 強勢篩選核心
        is_bull = curr['Close'] > curr['MA20'] and curr['MA20_Slope'] > 0
        is_kd_ok = curr['K'] > curr['D']
        is_vol_ok = vol_ratio > 1.1
        
        if is_bull and is_kd_ok and ret >= threshold and is_vol_ok:
            atr_val = df['ATR'].iloc[-1]
            stock_data["符合條件"] = True
            stock_data["支撐"] = round(float(curr['Close'] - (atr_val * 2)), 2)
            stock_data["目標"] = round(float(curr['Close'] + (atr_val * 3.5)), 2)
            stock_data["評分"] = ret + (vol_ratio * 2) + (curr['K'] / 10)
            return stock_data
        
        # 僅回傳基礎數據供統計
        stock_data["符合條件"] = False
        return stock_data
    except: return None

# --- 6. 主介面 ---
st.title("🏹 2026 美股強勢波段雷達 (抗跌分析版)")
market_msg, market_color, spy_ret = get_market_regime()
st.markdown(f"**市場環境：<span style='color:{market_color};'>{market_msg}</span> | 今日大盤漲跌：`{spy_ret:.2f}%`**", unsafe_allow_html=True)

df_all = get_full_data()

with st.sidebar:
    st.header("⚙️ 篩選參數")
    if df_all is not None:
        sector_options = ["全部產業", "全部 ETF"] + sorted([s for s in df_all['Sector_CN'].unique().tolist() if "ETF" not in str(s) and s != "全部產業"])
        selected_sector = st.selectbox("選擇產業別", sector_options)
    
    ret_target = st.slider("突破漲幅門檻 (%)", -1.0, 5.0, 0.0, 0.1)
    scan_limit = st.slider("掃描數量", 10, 550, 550)
    if st.button("🔄 重置快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始全市場深度掃描", use_container_width=True):
    if df_all is not None:
        if selected_sector == "全部 ETF":
            target_df = df_all[df_all['GICS Sector'].str.contains("ETF", na=False)]
        elif selected_sector != "全部產業":
            target_df = df_all[df_all['Sector_CN'] == selected_sector]
        else:
            target_df = df_all
            
        tickers_dict = dict(zip(target_df['Symbol'], target_df.iloc[:, 1]))
        sector_dict = dict(zip(target_df['Symbol'], target_df['Sector_CN']))
        tickers = list(tickers_dict.keys())[:scan_limit]
        
        results, sector_stats = [], []
        progress_bar = st.progress(0)
        
        data = yf.download(tickers, period="8mo", group_by='ticker', auto_adjust=True, progress=False)
        
        for i, sym in enumerate(tickers):
            try:
                df_stock = data[sym].dropna() if len(tickers) > 1 else data.dropna()
                res = analyze_stock_full(df_stock, ret_target, spy_ret)
                if res:
                    res["代碼"], res["名稱"], res["產業"] = sym, CN_NAME_MAP.get(sym, tickers_dict[sym]), sector_dict[sym]
                    if res["符合條件"]: results.append(res)
                    sector_stats.append({"產業": res["產業"], "漲幅": res["漲幅"]})
            except: continue
            progress_bar.progress((i + 1) / len(tickers))
        
        # --- 產業熱力統計 ---
        st.subheader("📊 產業強弱排行 (目前資金流向)")
        if sector_stats:
            stat_df = pd.DataFrame(sector_stats).groupby("產業").mean().sort_values("漲幅", ascending=False)
            cols = st.columns(len(stat_df) if len(stat_df) < 5 else 5)
            for idx, (name, row) in enumerate(stat_df.head(5).iterrows()):
                cols[idx % 5].metric(name, f"{row['漲幅']:.2f}%")
        
        # --- 掃描結果 ---
        st.divider()
        if results:
            results = sorted(results, key=lambda x: x['評分'], reverse=True)
            st.success(f"🎯 找到 {len(results)} 檔符合「帶量起漲」標的")
            now_str = datetime.now().strftime("%Y%m%d_%H%M")
            st.download_button("📥 匯出 CSV", pd.DataFrame(results).to_csv(index=False).encode('utf-8-sig'), f"stocks_{now_str}.csv", "text/csv")
            
            for item in results:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 1, 1])
                    with c1:
                        st.subheader(f"{item['代碼']} {item['名稱']}")
                        st.markdown(f'<span class="sector-badge">{item["產業"]}</span> <span class="vol-badge">量能比: {item["量能比"]}x</span>', unsafe_allow_html=True)
                        st.write(f"📈 相對大盤: `{item['相對大盤']}%` | 🛡️ 支撐: `${item['支撐']}`")
                    with c2:
                        st.metric("現價", f"${item['現價']}", f"{item['漲幅']}%")
                    with c3:
                        st.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 互動線圖</a>', unsafe_allow_html=True)
        else:
            st.warning("❌ 目前環境無符合「帶量多頭」標的。觀察上方產業排行，找尋相對抗跌板塊。")

st.caption("⚠ 策略建議：大盤空頭時，應優先關注『相對大盤』為正數且產業排行前三名的個股。")
