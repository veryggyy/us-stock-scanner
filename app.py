import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import os
from datetime import datetime

# --- 1. 頁面設定 ---
st.set_page_config(page_title="2026 美股強勢波段雷達", layout="wide")

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
    </style>
""", unsafe_allow_html=True)

# --- 2. 中文名稱對照表 ---
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
        if spy.empty: return "⚠️ 無法取得大盤數據", "#FFFFFF"
        spy['MA20'] = ta.sma(spy['Close'], length=20)
        curr, ma20 = spy['Close'].iloc[-1], spy['MA20'].iloc[-1]
        if curr > ma20:
            return "🟢 大盤位於月線上 (多頭策略)", "#00FFCC"
        else:
            return "🔴 大盤位於月線下 (空頭防禦)", "#FF4B4B"
    except: return "⚠️ 數據超載，暫時無法分析大盤", "#FFFFFF"

# --- 5. 核心分析引擎 (加入帶量指標) ---
def analyze_stock_with_volume(df, threshold):
    try:
        if df is None or len(df) < 200: return None
        df.columns = [str(c).capitalize() for c in df.columns]
        
        # 指標計算
        df['MA20'] = ta.sma(df['Close'], length=20)
        df['MA200'] = ta.sma(df['Close'], length=200)
        df['MA20_Slope'] = df['MA20'].diff(3)
        df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        kd = ta.stoch(df['High'], df['Low'], df['Close'], k=14, d=3, smooth_k=3)
        df['K'], df['D'] = kd.iloc[:, 0], kd.iloc[:, 1]
        
        # --- 量能指標計算 ---
        df['VMA5'] = ta.sma(df['Volume'], length=5) # 5日均量
        
        curr, prev = df.iloc[-1], df.iloc[-2]
        ret = (float(curr['Close']) / float(prev['Close']) - 1) * 100
        vol_ratio = round(float(curr['Volume'] / curr['VMA5']), 2) # 量能比
        
        # 篩選核心邏輯
        is_ma_ok = curr['Close'] > curr['MA20'] and curr['MA20_Slope'] > 0
        is_long_ok = curr['Close'] > curr['MA200']
        is_kd_ok = curr['K'] > curr['D'] and curr['K'] < 85
        is_vol_ok = vol_ratio > 1.1 # 帶量過濾：成交量需大於 5 日均量的 1.1 倍
        
        if is_ma_ok and is_long_ok and is_kd_ok and ret >= threshold and is_vol_ok:
            atr_val = df['ATR'].iloc[-1]
            # 評分系統加權：漲幅 + (量能比 * 2) + (K值權重)
            score = ret + (vol_ratio * 2) + (curr['K'] / 10)
            
            return {
                "現價": round(float(curr['Close']), 2),
                "漲幅": round(ret, 2),
                "量能比": vol_ratio,
                "K值": int(curr['K']),
                "支撐": round(float(curr['Close'] - (atr_val * 2)), 2),
                "目標": round(float(curr['Close'] + (atr_val * 3.5)), 2),
                "評分": score
            }
    except: return None
    return None

# --- 6. 主介面 ---
st.title("🏹 2026 美股帶量強勢波段雷達")
market_msg, market_color = get_market_regime()
st.markdown(f"**市場環境：<span style='color:{market_color};'>{market_msg}</span>**", unsafe_allow_html=True)

df_all = get_full_data()

with st.sidebar:
    st.header("⚙️ 篩選參數")
    if df_all is not None:
        sector_options = ["全部產業", "全部 ETF"] + sorted([s for s in df_all['Sector_CN'].unique().tolist() if "ETF" not in str(s) and s != "全部產業"])
        selected_sector = st.selectbox("選擇產業別", sector_options)
    
    ret_target = st.slider("突破漲幅門檻 (%)", -1.0, 5.0, 0.5, 0.1)
    scan_limit = st.slider("掃描數量", 10, 550, 550)
    if st.button("🔄 重置快取"): st.cache_data.clear(); st.rerun()

if st.button("🚀 開始帶量多頭掃描 (排序由強至弱)", use_container_width=True):
    if df_all is not None:
        if selected_sector == "全部 ETF":
            target_df = df_all[df_all['GICS Sector'].str.contains("ETF", na=False)]
        elif selected_sector != "全部產業":
            target_df = df_all[df_all['Sector_CN'] == selected_sector]
        else:
            target_df = df_all
            
        tickers_dict = dict(zip(target_df['Symbol'], target_df.iloc[:, 1]))
        tickers = list(tickers_dict.keys())[:scan_limit]
        
        st.info(f"正在分析「{selected_sector}」中的 {len(tickers)} 檔標的...")
        results = []
        progress_bar = st.progress(0)
        
        # 下載 10 個月數據確保 MA200/VMA5 可計算
        data = yf.download(tickers, period="10mo", group_by='ticker', auto_adjust=True, progress=False)
        
        for i, sym in enumerate(tickers):
            try:
                df_stock = data[sym].dropna() if len(tickers) > 1 else data.dropna()
                res = analyze_stock_with_volume(df_stock, ret_target)
                if res:
                    res["代碼"] = sym
                    res["名稱"] = CN_NAME_MAP.get(sym, tickers_dict[sym])
                    results.append(res)
            except: continue
            progress_bar.progress((i + 1) / len(tickers))
            
        if results:
            results = sorted(results, key=lambda x: x['評分'], reverse=True)
            st.success(f"🎯 找到 {len(results)} 檔「帶量起漲」符合標的")
            
            # 檔名時間戳記 (24H)
            now_str = datetime.now().strftime("%Y%m%d_%H%M")
            filename = f"strong_stocks_vol_{now_str}.csv"
            
            res_df = pd.DataFrame(results)
            st.download_button(
                label="📥 匯出強勢清單 (CSV)",
                data=res_df.to_csv(index=False).encode('utf-8-sig'),
                file_name=filename,
                mime="text/csv"
            )
            
            for item in results:
                with st.container(border=True):
                    c1, c2, c3 = st.columns()
                    with c1:
                        st.subheader(f"{item['代碼']} {item['名稱']}")
                        # 顯示量能比標籤
                        vol_text = f"量能比: {item['量能比']}x"
                        st.markdown(f'<span class="vol-badge">{vol_text}</span>', unsafe_allow_html=True)
                        st.write(f"📈 K值: `{item['K值']}` | 🛡️ 支撐: `${item['支撐']}` | 🎯 目標: `${item['目標']}`")
                    with c2:
                        st.metric("現價", f"${item['現價']}", f"{item['漲幅']}%")
                    with c3:
                        st.markdown(f'<br><a href="https://www.tradingview.com{item["代碼"]}" target="_blank" class="tv-link">📊 互動線圖</a>', unsafe_allow_html=True)
                        st.markdown(f"[📰 Yahoo 新聞](https://finance.yahoo.com{item['代碼']}/news)", unsafe_allow_html=True)
        else:
            st.warning("目前環境下無符合「帶量多頭」標的。")

st.divider()
st.caption("⚠ 免責聲明：此工具僅供參考。量能比大於 1 代表熱度升溫，大於 1.5 為明顯異常放量起漲。")
