import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import requests
import io

try:
    from sklearn.ensemble import RandomForestClassifier
except ImportError:
    pass

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

st.set_page_config(page_title="V3004 APEX GLOBAL - QUANTUM FON", layout="wide", page_icon="🐺")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #ff3366; margin: 10px 0; text-shadow: 0 0 15px rgba(255, 51, 102, 0.3); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #ff3366; padding: 25px; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    
    .ai-report { background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); border: 1px solid #2d3748; border-top: 3px solid #ff3366; padding: 25px; margin-top: 20px; border-radius: 10px; font-size: 15px; line-height: 1.6; color: #e2e8f0; }
    .report-card { background: rgba(0,0,0,0.3); border: 1px solid #2d3748; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 3px solid #d4af37;}
    .report-title { color: #ff3366; font-weight: 900; font-size: 18px; margin-bottom: 5px;}
    
    .manual-panel { background: #11161d; border: 1px dashed #4a5568; padding: 20px; border-radius: 10px; margin-top: 15px; }
    
    .stat-box { background: rgba(0,0,0,0.4); border: 1px solid #2d3748; padding: 15px; border-radius: 8px; text-align: center; }
    .stat-box b { color: #8b949e; font-size: 14px; text-transform: uppercase; }
    .stat-box span { display: block; font-size: 28px; font-weight: 900; color: #00ffcc; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource(ttl=600)
def init_google_sheets():
    if not GSPREAD_INSTALLED: return None
    try:
        if "gcp_service_account" in st.secrets:
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
            creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            return gspread.authorize(creds).open("Quantum_Bilanco").sheet1
    except: return None
sheet = init_google_sheets()
all_vals = sheet.get_all_values() if sheet else []

if 'lokal_kasa' not in st.session_state:
    if len(all_vals) > 0:
        last_row = all_vals[-1]
        st.session_state.lokal_kasa = float(str(last_row[5]).replace(',','.')) if len(last_row) > 5 else 10000.0
        st.session_state.bekleyen_tutar = float(str(last_row[6]).replace(',','.')) if len(last_row) > 6 else 0.0
        st.session_state.baslangic_kasa = float(str(last_row[7]).replace(',','.')) if len(last_row) > 7 else st.session_state.lokal_kasa
    else: st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa = 10000.0, 0.0, 10000.0

if 'raw_api_data' not in st.session_state: st.session_state.raw_api_data = []

API_LEAGUES = {
    "İngiltere Premier Lig": "soccer_epl", 
    "İngiltere Championship": "soccer_efl_championship",
    "İngiltere League One": "soccer_england_league1",
    "İngiltere League Two": "soccer_england_league2",
    "Türkiye Süper Lig": "soccer_turkey_super_league", 
    "Türkiye 1. Lig": "soccer_turkey_1_lig",
    "Almanya Bundesliga": "soccer_germany_bundesliga", 
    "İspanya La Liga": "soccer_spain_la_liga",
    "İtalya Serie A": "soccer_italy_serie_a", 
    "Fransa Ligue 1": "soccer_france_ligue_one",
    "Hollanda Eredivisie": "soccer_netherlands_eredivisie", 
    "Belçika Pro Lig": "soccer_belgium_first_division_a",
    "Portekiz Primeira Liga": "soccer_portugal_primeira_liga",
    "İskoçya Premiership": "soccer_spl",
    "Yunanistan Süper Lig": "soccer_greece_super_league"
}

@st.cache_data(ttl=86400, show_spinner=False)
def load_and_train_ml_model():
    leagues_codes = ['E0', 'E1', 'E2', 'E3', 'T1', 'D1', 'SP1', 'I1', 'F1', 'N1', 'B1', 'P1', 'SC0', 'G1']
    seasons = ['2223', '2324', '2425', '2526']
    urls = []
    
    for code in leagues_codes:
        for season in seasons:
            urls.append(f'https://www.football-data.co.uk/mmz4281/{season}/{code}.csv') 
        
    dfs = []
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                # HTR (İlk Yarı Sonucu) veritabanına eklendi
                if 'B365H' in df.columns: 
                    dfs.append(df[['B365H', 'B365D', 'B365A', 'FTR', 'FTHG', 'FTAG', 'HTR']].dropna())
        except: pass
    
    if not dfs: return None, None, None, None, None, None
    df_train = pd.concat(dfs, ignore_index=True)
    
    weights = np.linspace(0.3, 1.5, len(df_train))
    
    X = df_train[['B365H', 'B365D', 'B365A']]
    y_taraf = df_train['FTR'].map({'H': 0, 'D': 1, 'A': 2}) 
    y_gol_25 = ((df_train['FTHG'] + df_train['FTAG']) > 2.5).astype(int) 
    y_gol_15 = ((df_train['FTHG'] + df_train['FTAG']) > 1.5).astype(int) 
    y_gol_35 = ((df_train['FTHG'] + df_train['FTAG']) > 3.5).astype(int) 
    y_kg = ((df_train['FTHG'] > 0) & (df_train['FTAG'] > 0)).astype(int) 
    
    rf_taraf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf_gol_25 = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf_gol_15 = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf_gol_35 = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf_kg = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    
    rf_taraf.fit(X, y_taraf, sample_weight=weights)
    rf_gol_25.fit(X, y_gol_25, sample_weight=weights)
    rf_gol_15.fit(X, y_gol_15, sample_weight=weights)
    rf_gol_35.fit(X, y_gol_35, sample_weight=weights)
    rf_kg.fit(X, y_kg, sample_weight=weights)
    
    # HATA ÇÖZÜMÜ BURADA: Doğru değişken isimleri döndürüldü
    return df_train, rf_taraf, rf_gol_25, rf_gol_15, rf_gol_35, rf_kg

df_history, model_taraf, model_gol25, model_gol15, model_gol35, model_kg = load_and_train_ml_model()

# API KREDİ KALKANI: Skorlar 30 dakika boyunca önbellekte kalır
@st.cache_data(ttl=1800, show_spinner=False)
def get_cached_scores(api_key, lig):
    url = f"https://api.the-odds-api.com/v4/sports/{lig}/scores/?apiKey={api_key.strip()}&daysFrom=3"
    try:
        resp = requests.get(url, timeout=5).json()
        if isinstance(resp, list): return resp
    except: pass
    return []

def check_match_result_optimized(home, away, target_market, lig_skor_havuzu):
    if not lig_skor_havuzu: return "BEKLİYOR", "-"
    for m in lig_skor_havuzu:
        if m['home_team'] == home and m['away_team'] == away:
            if m.get('completed', False):
                scores = m.get('scores', [])
                if not scores: return "BEKLİYOR", "-"
                h_score = int(scores[0]['score']) if scores[0]['name'] == home else int(scores[1]['score'])
                a_score = int(scores[1]['score']) if scores[1]['name'] == away else int(scores[0]['score'])
                total = h_score + a_score
                won = False
                if target_market == "2.5 Üst" and total > 2: won = True
                elif target_market == "2.5 Alt" and total < 3: won = True
                elif target_market == "3.5 Üst" and total > 3: won = True
                elif target_market == "3.5 Alt" and total < 4: won = True
                elif target_market == "1.5 Üst" and total > 1: won = True
                elif target_market == "KG Var" and h_score > 0 and a_score > 0: won = True
                elif target_market == "KG Yok" and (h_score == 0 or a_score == 0): won = True
                elif target_market == "MS 1" and h_score > a_score: won = True
                elif target_market == "MS 2" and a_score > h_score: won = True
                elif target_market == "MS 0" and h_score == a_score: won = True
                return ("KAZANDI" if won else "KAYBETTİ"), f"{h_score}-{a_score}"
    return "BEKLİYOR", "Maç Bitmedi"

st.markdown("<h1 style='text-align:center; color:#ff3366; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(255, 51, 102, 0.4);'>🐺 V3004 APEX GLOBAL</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>4 Yıllık Derin Arşiv | Alt Lig (Karanlık Maden) Tarayıcısı</p><br>", unsafe_allow_html=True)

# 6. Sekme Eklendi
tab1, tab5, tab2, tab4, tab3, tab6 = st.tabs(["📡 1. PİYASA TARAMASI", "📊 5. GEÇMİŞ ORAN ARŞİVİ", "🧠 2. DERİN ANALİZ", "🤖 3. OTO-PİLOT", "📈 4. BİLANÇO", "⏱️ 6. İY/MS RADARI"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Ligleri Seçin:", list(API_LEAGUES.keys()), default=list(API_LEAGUES.keys())[:8])
with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password", key="odds_api_key")

with tab1:
    if st.button("📡 GÜNÜN MAÇLARINI ÇEK", use_container_width=True):
        if not api_key: st.error("API Anahtarı eksik!")
        else:
            with st.spinner("Büyük Veri radarı aktif... Tüm oranlar çekiliyor..."):
                toplanan_maclar = []
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now_tr = now_utc + datetime.timedelta(hours=3)
                
                for lig in secilen_ligler:
                    try:
                        url = f"https://api.the-odds-api.com/v4/sports/{API_LEAGUES[lig]}/odds/?apiKey={api_key.strip()}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
                        resp = requests.get(url).json()
                        if isinstance(resp, list):
                            for m in resp:
                                m['kendi_ligi'] = lig
                                m_time = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                                m_time_tr = m_time + datetime.timedelta(hours=3)
                                if now_utc < m_time and now_tr.date() == m_time_tr.date():
                                    toplanan_maclar.append(m)
                    except: pass
                st.session_state.raw_api_data = toplanan_maclar
                st.success(f"✅ Sistem Hazır. Toplam {len(toplanan_maclar)} eşleşme yakalandı.")

with tab5:
    st.markdown("### 📊 GEÇMİŞ ORAN ARŞİVİ (4 YILLIK BÜYÜK VERİ)")
    
    st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
    mac_isimleri_5 = ["Manuel Oran Gireceğim"] + [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
    secilen_mac_str_5 = st.selectbox("🎯 İstersen Günün Maçlarından Birini Seç:", mac_isimleri_5)
    
    oto_h, oto_d, oto_a = 2.10, 3.20, 2.80
    if secilen_mac_str_5 != "Manuel Oran Gireceğim":
        secilen_m = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str_5)
        try:
            for bkm in secilen_m.get('bookmakers', []):
                for mkt in bkm.get('markets', []):
                    if mkt['key'] == 'h2h':
                        for out in mkt['outcomes']:
                            if out['name'] == secilen_m['home_team']: oto_h = out['price']
                            elif out['name'] == secilen_m['away_team']: oto_a = out['price']
                            elif out['name'] == 'Draw': oto_d = out['price']
        except: pass

    c_h, c_d, c_a, c_tol = st.columns(4)
    with c_h: s_h = st.number_input("MS 1 Oranı:", min_value=1.01, value=float(oto_h), step=0.05)
    with c_d: s_d = st.number_input("MS 0 Oranı:", min_value=1.01, value=float(oto_d), step=0.05)
    with c_a: s_a = st.number_input("MS 2 Oranı:", min_value=1.01, value=float(oto_a), step=0.05)
    with c_tol: tolerans = st.number_input("Esneklik (± Oran):", min_value=0.0, value=0.05, step=0.01)
    st.markdown("</div><br>", unsafe_allow_html=True)

    if st.button("🔍 4 YILLIK ARŞİVİ TARA (BİG DATA)", use_container_width=True):
        if df_history is None:
            st.error("Makine Öğrenimi veritabanı yüklenemedi.")
        else:
            with st.spinner(f"Veritabanında oran aranıyor..."):
                mask = (
                    (df_history['B365H'] >= s_h - tolerans) & (df_history['B365H'] <= s_h + tolerans) &
                    (df_history['B365D'] >= s_d - tolerans) & (df_history['B365D'] <= s_d + tolerans) &
                    (df_history['B365A'] >= s_a - tolerans) & (df_history['B365A'] <= s_a + tolerans)
                )
                filtered_df = df_history[mask]
                
                toplam_mac = len(filtered_df)
                if toplam_mac > 0:
                    ms1_yuzde = (len(filtered_df[filtered_df['FTR'] == 'H']) / toplam_mac) * 100
                    ms0_yuzde = (len(filtered_df[filtered_df['FTR'] == 'D']) / toplam_mac) * 100
                    ms2_yuzde = (len(filtered_df[filtered_df['FTR'] == 'A']) / toplam_mac) * 100
                    ust25_yuzde = (len(filtered_df[(filtered_df['FTHG'] + filtered_df['FTAG']) > 2.5]) / toplam_mac) * 100
                    kgvar_yuzde = (len(filtered_df[(filtered_df['FTHG'] > 0) & (filtered_df['FTAG'] > 0)]) / toplam_mac) * 100
                    
                    st.success(f"🎯 Veritabanında tam **{toplam_mac} maç** bulundu! Sonuçları:")
                    
                    c_r1, c_r2, c_r3, c_r4, c_r5 = st.columns(5)
                    with c_r1: st.markdown(f"<div class='stat-box'><b>MS 1 İhtimali</b><span>%{ms1_yuzde:.1f}</span></div>", unsafe_allow_html=True)
                    with c_r2: st.markdown(f"<div class='stat-box'><b>MS 0 İhtimali</b><span style='color:#ffcc00;'>%{ms0_yuzde:.1f}</span></div>", unsafe_allow_html=True)
                    with c_r3: st.markdown(f"<div class='stat-box'><b>MS 2 İhtimali</b><span style='color:#ff3366;'>%{ms2_yuzde:.1f}</span></div>", unsafe_allow_html=True)
                    with c_r4: st.markdown(f"<div class='stat-box'><b>2.5 ÜST İhtimali</b><span>%{ust25_yuzde:.1f}</span></div>", unsafe_allow_html=True)
                    with c_r5: st.markdown(f"<div class='stat-box'><b>KG VAR İhtimali</b><span>%{kgvar_yuzde:.1f}</span></div>", unsafe_allow_html=True)
                else:
                    st.warning("MAÇ BULUNAMADI.")

with tab2:
    if len(st.session_state.raw_api_data) == 0:
        st.info("Lütfen 1. Sekmeden piyasa verilerini çekin.")
    elif model_taraf is None:
        st.error("🚨 Makine Öğrenimi modeli eğitilemedi.")
    else:
        mac_isimleri = [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
        secilen_mac_str = st.selectbox("🎯 Gelişmiş xG Analizi İçin Maç Seçin:", mac_isimleri)
        
        if secilen_mac_str:
            secilen_mac = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str)
            
            st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color:#ff3366;'>🔬 Aşama 1: xG (Gol Beklentisi) Veri Girişi</h3>", unsafe_allow_html=True)
            
            c_f1, c_f2 = st.columns(2)
            with c_f1: min_oran_manuel = st.number_input("Minimum Oran Filtresi:", min_value=1.00, value=1.50, step=0.10)
            with c_f2: guven_esigi = st.slider("Güvenlik Eşiği Belirle (%):", min_value=25, max_value=90, value=40, step=1)
            
            st.divider()

            c_ev, c_dep = st.columns(2)
            with c_ev:
                st.markdown(f"**🏠 {secilen_mac['home_team']}**")
                ev_mac = st.number_input("Son Kaç Maç?:", min_value=1, value=5, key="ev_mac")
                ev_at = st.number_input("Attığı Gol:", min_value=0, value=8, key="ev_at")
                ev_sut = st.number_input("Ort. İsabetli Şut:", min_value=0.0, value=4.5, step=0.5, key="ev_sut")
                ev_ye = st.number_input("Yediği Gol:", min_value=0, value=4, key="ev_ye")
                
            with c_dep:
                st.markdown(f"**✈️ {secilen_mac['away_team']}**")
                dep_mac = st.number_input("Son Kaç Maç?:", min_value=1, value=5, key="dep_mac")
                dep_at = st.number_input("Attığı Gol:", min_value=0, value=5, key="dep_at")
                dep_sut = st.number_input("Ort. İsabetli Şut:", min_value=0.0, value=3.5, step=0.5, key="dep_sut")
                dep_ye = st.number_input("Yediği Gol:", min_value=0, value=7, key="dep_ye")
            
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if st.button("🔮 KUSURSUZ xG RADARINI BAŞLAT", use_container_width=True):
                with st.spinner("Makine xG simülasyonunu yapıyor..."):
                    h_odd, d_odd, a_odd = 0, 0, 0 
                    try:
                        for bkm in secilen_mac.get('bookmakers', []):
                            for mkt in bkm.get('markets', []):
                                if mkt['key'] == 'h2h':
                                    for out in mkt['outcomes']:
                                        if out['name'] == secilen_mac['home_team']: h_odd = out['price']
                                        elif out['name'] == secilen_mac['away_team']: a_odd = out['price']
                                        elif out['name'] == 'Draw': d_odd = out['price']
                    except: pass
                    
                    if h_odd == 0: h_odd, d_odd, a_odd = 2.50, 3.20, 2.80

                    ev_xg_proxy = ((ev_at / ev_mac) * 0.5) + (ev_sut * 0.2) if ev_mac > 0 else 1.0
                    ev_def_ort = ev_ye / ev_mac if ev_mac > 0 else 1.0
                    
                    dep_xg_proxy = ((dep_at / dep_mac) * 0.5) + (dep_sut * 0.2) if dep_mac > 0 else 1.0
                    dep_def_ort = dep_ye / dep_mac if dep_mac > 0 else 1.0
                    
                    lambda_home = max(0.1, (ev_xg_proxy + dep_def_ort) / 2.0)
                    lambda_away = max(0.1, (dep_xg_proxy + ev_def_ort) / 2.0)

                    p_ms1=0.0; p_ms2=0.0; p_ms0=0.0
                    p_15ust=0.0; p_25ust=0.0; p_35ust=0.0; p_kgvar=0.0
                    
                    for h in range(8):
                        for a in range(8):
                            prob = poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)
                            if h > a: p_ms1 += prob
                            elif h < a: p_ms2 += prob
                            else: p_ms0 += prob
                            total = h + a
                            if total > 1.5: p_15ust += prob
                            if total > 2.5: p_25ust += prob
                            if total > 3.5: p_35ust += prob
                            if h > 0 and a > 0: p_kgvar += prob

                    poisson_probs = {
                        "MS 1": p_ms1, "MS 2": p_ms2, "MS 0": p_ms0,
                        "1.5 Üst": p_15ust, "2.5 Üst": p_25ust, "2.5 Alt": (1-p_25ust),
                        "3.5 Üst": p_35ust, "3.5 Alt": (1-p_35ust),
                        "KG Var": p_kgvar, "KG Yok": (1-p_kgvar)
                    }

                    input_data = pd.DataFrame([[h_odd, d_odd, a_odd]], columns=['B365H', 'B365D', 'B365A'])
                    ml_taraf_probs = model_taraf.predict_proba(input_data)[0] 
                    ml_gol25_probs = model_gol25.predict_proba(input_data)[0]     
                    ml_gol15_probs = model_gol15.predict_proba(input_data)[0]
                    ml_gol35_probs = model_gol35.predict_proba(input_data)[0]
                    ml_kg_probs = model_kg.predict_proba(input_data)[0]       

                    ml_probs = {
                        "MS 1": ml_taraf_probs[0], "MS 0": ml_taraf_probs[1], "MS 2": ml_taraf_probs[2],
                        "2.5 Üst": ml_gol25_probs[1], "2.5 Alt": ml_gol25_probs[0],
                        "1.5 Üst": ml_gol15_probs[1], "1.5 Alt": ml_gol15_probs[0],
                        "3.5 Üst": ml_gol35_probs[1], "3.5 Alt": ml_gol35_probs[0],
                        "KG Var": ml_kg_probs[1], "KG Yok": ml_kg_probs[0]
                    }

                    THRESHOLD = guven_esigi / 100.0
                    gecen_hedefler = []
                    
                    for pazar in poisson_probs.keys():
                        ort_ihtimal = (poisson_probs[pazar] + ml_probs[pazar]) / 2.0
                        
                        temp_oran = 1.0
                        if pazar == "MS 1": temp_oran = h_odd
                        elif pazar == "MS 0": temp_oran = d_odd
                        elif pazar == "MS 2": temp_oran = a_odd
                        else: 
                            if ort_ihtimal > 0.05:
                                adil_oran = 1.0 / ort_ihtimal
                                temp_oran = round(adil_oran * 0.93, 2)
                                if temp_oran < 1.01: temp_oran = 1.01
                            else: temp_oran = 1.50
                        
                        if temp_oran < min_oran_manuel: continue
                        if pazar == "MS 0" and (h_odd < 1.70 or a_odd < 1.70): continue 
                        if pazar == "MS 1" and (ev_xg_proxy < dep_xg_proxy): continue 
                        if pazar == "MS 2" and (dep_xg_proxy < ev_xg_proxy): continue 
                        if pazar == "2.5 Üst" and (lambda_home + lambda_away < 2.0): continue 
                        if pazar == "KG Var" and (ev_xg_proxy < 0.8 or dep_xg_proxy < 0.8): continue 
                        
                        if ort_ihtimal >= THRESHOLD:
                            gecen_hedefler.append((pazar, ort_ihtimal, poisson_probs[pazar], ml_probs[pazar], temp_oran))
                            
                    gecen_hedefler = sorted(gecen_hedefler, key=lambda x: x[1], reverse=True)
                    
                    if len(gecen_hedefler) > 0:
                        rapor = f"🧠 <b>V3004 APEX - MANTIK FİLTRELİ SONUÇLAR</b><br><br>"
                        rapor += f"📊 <b>xG Beklentisi:</b> Ev ({lambda_home:.2f}) - Dep ({lambda_away:.2f})<br>"
                        rapor += f"📡 <b>İddaa Oranları:</b> Ev ({h_odd:.2f}) | Brb ({d_odd:.2f}) | Dep ({a_odd:.2f})<br><br>"
                        
                        for pazar, final_prob, p_prob, ml_prob, t_oran in gecen_hedefler:
                            fark = ml_prob - p_prob
                            if abs(fark) < 0.10: durum = "<span style='color:#00ffcc;'>🟢 ML ve xG Mutabık</span>"
                            elif fark > 0.10: durum = "<span style='color:#ff3366;'>🔥 Derin Öğrenme Destekliyor</span>"
                            else: durum = "<span style='color:#ffcc00;'>🟡 xG Formu Daha Ağır Basıyor</span>"
                            
                            rapor += f"""
                            <div class='report-card'>
                                <div class='report-title'>[{pazar}] ➜ Adil Oran: {t_oran:.2f} | Güven: %{int(final_prob*100)}</div>
                                <b>Sistem Durumu:</b> {durum}<br>
                                <span style='font-size:13px; color:#a0aec0;'>[xG/Poisson İhtimali: %{int(p_prob*100)} | ML Ağ İhtimali: %{int(ml_prob*100)}]</span>
                            </div>
                            """
                        secilen_mac['gecen_hedefler'] = gecen_hedefler
                        secilen_mac['ai_rapor'] = rapor
                        st.session_state.aktif_mac = secilen_mac 
                        st.success(f"🐺 Radar tamamlandı!")
                    else:
                        st.session_state.aktif_mac = None
                        st.error(f"🚨 UYARI: Bu maç filtreleri geçemedi.")

        if 'aktif_mac' in st.session_state and st.session_state.aktif_mac is not None:
            m = st.session_state.aktif_mac
            st.divider()
            
            st.markdown(f"<div class='match-card'><div class='match-title'>{m['home_team']} ⚡ {m['away_team']}</div><br>", unsafe_allow_html=True)
            st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div><br>", unsafe_allow_html=True)
            
            hedef_opsiyonlari = [f"{h[0]} (Oran: {h[4]:.2f} | Güven: %{int(h[1]*100)})" for h in m['gecen_hedefler']]
            secilen_hedef_str = st.selectbox("📌 APEX HEDEFİNİ ONAYLA:", hedef_opsiyonlari, key="nihai_hedef_secim")
            
            nihai_pazar = secilen_hedef_str.split(' (')[0].strip()
            nihai_prob_str = secilen_hedef_str.split('Güven: %')[1].split(')')[0]
            nihai_prob = float(nihai_prob_str) / 100.0
            
            c_oran, c_bos = st.columns([1, 1])
            with c_oran:
                secilen_tuple = next(item for item in m['gecen_hedefler'] if item[0] == nihai_pazar)
                hesaplanan_adil_oran = secilen_tuple[4]
                m['manuel_oran'] = st.number_input(f"Seçtiğin [{nihai_pazar}] hedefinin İddaa'daki Gerçek Oranını Girin:", min_value=1.00, value=hesaplanan_adil_oran, step=0.01, key="iddaa_guncel_oran")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("### 🚀 Otonom Vur Kaç (Flat Betting)")
            manuel_tutar = st.number_input("💵 İşlem Tutarı (Birim/Unit):", min_value=10.0, value=100.0, step=10.0, key="tutar_tekli")
            
            c_btn_real, c_btn_shadow = st.columns(2)
            with c_btn_real: btn_gercek = st.button("🚀 ONAYLA (Gerçek Kasa)", use_container_width=True, key="onay_gercek_tek")
            with c_btn_shadow: btn_sanal = st.button("👻 GÖLGE MODU (Eğitim)", use_container_width=True, key="onay_sanal_tek")
                
            if btn_gercek or btn_sanal:
                yatirilacak_tutar = manuel_tutar if btn_gercek else 0.0
                durum_text = "Bekliyor" if btn_gercek else "Sanal_Bekliyor"
                
                if btn_gercek:
                    st.session_state.lokal_kasa -= yatirilacak_tutar
                    st.session_state.bekleyen_tutar += yatirilacak_tutar
                
                if sheet:
                    isimler = f"{m['home_team']} vs {m['away_team']}"
                    ligler = m['sport_key']
                    tercihler = nihai_pazar 
                    problar = f"{nihai_prob:.3f}"
                    oranlar = f"{m.get('manuel_oran', 1.50):.2f}"
                    
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, oranlar, durum_text, "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, oranlar])
                
                st.session_state.aktif_mac = None
                st.success(f"İşlem Başarılı! APEX tahmini sisteme ateşlendi.")
                st.rerun()

with tab4:
    st.markdown("### 🤖 OTO-PİLOT (APEX V3004)")
    c_oto1, c_oto2 = st.columns(2)
    with c_oto1: oto_min_oran = st.number_input("Otonom Minimum Oran Sınırı:", min_value=1.0, value=1.50, step=0.1)
    with c_oto2: oto_esik = st.slider("APEX Otomatik Onay Eşiği (%):", min_value=30, max_value=90, value=45, step=1)
    
    if st.button("🚀 BÜTÜN LİGLERDE APEX TARAMASI YAP", use_container_width=True):
        if len(st.session_state.raw_api_data) == 0: st.warning("Önce günün maçlarını çekmelisin!")
        elif model_taraf is None: st.error("Makine Öğrenimi aktif değil.")
        else:
            with st.spinner(f"Global Veri Ağı Devrede..."):
                oto_oynanan_maclar = 0
                oynanmis_kombinasyonlar = set()
                if all_vals:
                    for r in all_vals:
                        if len(r) > 10 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]:
                            oynanmis_kombinasyonlar.add(f"{r[8].strip()}_{r[10].strip()}")
                
                for m in st.session_state.raw_api_data:
                    h_odd, d_odd, a_odd = 0, 0, 0
                    try:
                        for bkm in m.get('bookmakers', []):
                            for mkt in bkm.get('markets', []):
                                if mkt['key'] == 'h2h':
                                    for out in mkt['outcomes']:
                                        if out['name'] == m['home_team']: h_odd = out['price']
                                        elif out['name'] == m['away_team']: a_odd = out['price']
                                        elif out['name'] == 'Draw': d_odd = out['price']
                    except: pass
                    
                    if h_odd == 0 or d_odd == 0 or a_odd == 0: continue
                    isimler = f"{m['home_team']} vs {m['away_team']}"
                    
                    input_data = pd.DataFrame([[h_odd, d_odd, a_odd]], columns=['B365H', 'B365D', 'B365A'])
                    ml_taraf_probs = model_taraf.predict_proba(input_data)[0] 
                    ml_gol25_probs = model_gol25.predict_proba(input_data)[0]     
                    ml_kg_probs = model_kg.predict_proba(input_data)[0]
                    
                    ml_probs = {
                        "MS 1": ml_taraf_probs[0], "MS 0": ml_taraf_probs[1], "MS 2": ml_taraf_probs[2],
                        "2.5 Üst": ml_gol25_probs[1], "2.5 Alt": ml_gol25_probs[0],
                        "KG Var": ml_kg_probs[1], "KG Yok": ml_kg_probs[0]
                    }
                    
                    THRESHOLD = oto_esik / 100.0
                    bulunan_hedefler = []
                    
                    for pazar, prob in ml_probs.items():
                        temp_oran = 1.0
                        if pazar == "MS 1": temp_oran = h_odd
                        elif pazar == "MS 0": temp_oran = d_odd
                        elif pazar == "MS 2": temp_oran = a_odd
                        else: 
                            if prob > 0.05:
                                temp_oran = round((1.0 / prob) * 0.93, 2)
                                if temp_oran < 1.01: temp_oran = 1.01
                            else: temp_oran = 1.50
                        
                        if temp_oran < oto_min_oran: continue
                        if pazar == "MS 0" and (h_odd < 1.70 or a_odd < 1.70): continue 
                        if pazar == "MS 1" and h_odd > a_odd: continue 
                        if pazar == "MS 2" and a_odd > h_odd: continue
                        
                        if prob >= THRESHOLD:
                            if f"{isimler}_{pazar}" not in oynanmis_kombinasyonlar:
                                bulunan_hedefler.append((pazar, prob, temp_oran))
                            
                    for pazar, prob, gercek_oran in bulunan_hedefler:
                        if sheet:
                            sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 100.0, f"{gercek_oran:.2f}", "Sanal_Bekliyor", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, m['sport_key'], pazar, f"{prob:.3f}", f"{gercek_oran:.2f}"])
                            oynanmis_kombinasyonlar.add(f"{isimler}_{pazar}")
                            oto_oynanan_maclar += 1
                
                if oto_oynanan_maclar > 0: st.success(f"🤖 {oto_oynanan_maclar} adet oran eklendi.")
                else: st.warning(f"Yeni maç kalmadı.")

with tab3:
    st.markdown("<h2 style='color:#d4af37;'>💼 Kuantum Fon Bilanço & Analitik</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    kasa, bekleyen, baslangic = st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa
    roi_genel = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GERÇEK KASA</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN GERÇEK YATIRIM</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>GENEL KASA BÜYÜMESİ</div><div class='metric-value'>% {roi_genel:.1f}</div></div>", unsafe_allow_html=True)
    
    st.divider()
    
    c_btn1, c_btn2 = st.columns([3,1])
    with c_btn1: st.markdown("<h3>📝 Bekleyen Operasyonlar (Denetçi)</h3>", unsafe_allow_html=True)
    with c_btn2:
        if st.button("🤖 OTONOM DENETÇİYİ ÇALIŞTIR", use_container_width=True, key="otonom_denetci_btn"):
            if not api_key: st.error("API Anahtarı eksik!")
            else:
                with st.spinner("Skorlar denetleniyor (Cache Sistemi Devrede)..."):
                    bekleyen_ligler = set()
                    for r in all_vals:
                        if len(r) > 12 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]:
                            for l in r[9].split('#'):
                                if l.strip(): bekleyen_ligler.add(l.strip())
                    
                    skor_havuzu = {}
                    for lig in bekleyen_ligler:
                        skor_havuzu[lig] = get_cached_scores(api_key, lig)

                    updates_made = False
                    for idx, r in enumerate(all_vals):
                        if len(r) > 12 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]:
                            is_sanal = (r[3] == "Sanal_Bekliyor")
                            b_tutar = float(str(r[1]).replace(',','.'))
                            b_oran = float(str(r[2]).replace(',','.'))
                            
                            durumlar, skorlar = [], []
                            for m_isim, m_lig, m_pazar in zip(r[8].split('#'), r[9].split('#'), r[10].split('#')):
                                if ' vs ' in m_isim:
                                    ev, dep = m_isim.split(' vs ')
                                    res, skor = check_match_result_optimized(ev, dep, m_pazar.strip(), skor_havuzu.get(m_lig.strip(), [])) 
                                else: res, skor = "BEKLİYOR", "-"
                                durumlar.append(res)
                                skorlar.append(skor)
                            
                            nihai_sonuc = "BEKLİYOR"
                            if "BEKLİYOR" not in durumlar and "Korner Manuel" not in skorlar:
                                if "KAYBETTİ" in durumlar: nihai_sonuc = "KAYBETTİ"
                                elif all(d == "KAZANDI" for d in durumlar): nihai_sonuc = "KAZANDI"
                            
                            if nihai_sonuc != "BEKLİYOR":
                                updates_made = True
                                sheet.update_cell(idx+1, 4, "Bekliyor_Kapandı" if not is_sanal else "Sanal_Kapandı")
                                net_kar = (b_tutar * b_oran) - b_tutar if nihai_sonuc == "KAZANDI" else -b_tutar
                                k_z_metni = f"+{net_kar:.2f}" if net_kar > 0 else f"{net_kar:.2f}"
                                yeni_satir = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), b_tutar, b_oran]
                                
                                if nihai_sonuc == "KAZANDI":
                                    if not is_sanal:
                                        st.session_state.lokal_kasa += (b_tutar * b_oran)
                                        st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                        yeni_satir.extend(["Kazandı_Sonuc", k_z_metni])
                                    else: yeni_satir.extend(["Sanal_Kazandı", k_z_metni]) 
                                else:
                                    if not is_sanal:
                                        st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                        yeni_satir.extend(["Kaybetti_Sonuc", k_z_metni])
                                    else: yeni_satir.extend(["Sanal_Kaybetti", k_z_metni]) 
                                    
                                yeni_satir.extend([st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa])
                                yeni_satir.extend([r[8] + f" (Skorlar: {' | '.join(skorlar)})"] + r[9:])
                                sheet.append_row(yeni_satir)
                    
                    if updates_made:
                        st.success("✅ Maçlar sonuçlandırıldı!")
                        st.rerun()
                    else: st.info("Maçlar henüz bitmemiş.")

# YEPYENİ 6. SEKME: SADECE GEÇMİŞ İSTATİSTİKLERE DAYALI İY/MS RADARI
with tab6:
    st.markdown("### ⏱️ KESKİN NİŞANCI: İY/MS RADARI")
    st.markdown("<p style='color:#a0aec0;'>Gözüne kestirdiğin maçı seç, geçmiş 4 yılda bu oranlara sahip maçlarda en çok hangi İY/MS senaryosunun geldiğini somut rakamlarla gör. (Sıfır yorum, sadece istatistik)</p>", unsafe_allow_html=True)

    if len(st.session_state.raw_api_data) == 0:
        st.info("Lütfen önce 1. Sekmeden günün piyasa verilerini çekin.")
    elif df_history is None:
        st.error("🚨 Makine Öğrenimi veritabanı yüklenemedi.")
    else:
        mac_isimleri_6 = [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
        secilen_mac_str_6 = st.selectbox("🎯 Hangi Maçın Geçmiş İY/MS İstatistiklerini Görmek İstiyorsun?:", ["Seçim Yapın..."] + mac_isimleri_6, key="iyms_mac_secim")

        if secilen_mac_str_6 != "Seçim Yapın...":
            secilen_m = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str_6)

            # API'den güncel MS oranlarını alıyoruz
            oto_h, oto_d, oto_a = 2.10, 3.20, 2.80
            try:
                for bkm in secilen_m.get('bookmakers', []):
                    for mkt in bkm.get('markets', []):
                        if mkt['key'] == 'h2h':
                            for out in mkt['outcomes']:
                                if out['name'] == secilen_m['home_team']: oto_h = out['price']
                                elif out['name'] == secilen_m['away_team']: oto_a = out['price']
                                elif out['name'] == 'Draw': oto_d = out['price']
            except: pass

            st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
            st.markdown("Bu maçın güncel İddaa oranları aşağıda otomatik dolduruldu. İstersen oranları kendin de değiştirebilirsin:")
            c_h2, c_d2, c_a2 = st.columns(3)
            with c_h2: man_h = st.number_input("MS 1 Oranı:", min_value=1.01, value=float(oto_h), step=0.05, key="man_h")
            with c_d2: man_d = st.number_input("MS 0 Oranı:", min_value=1.01, value=float(oto_d), step=0.05, key="man_d")
            with c_a2: man_a = st.number_input("MS 2 Oranı:", min_value=1.01, value=float(oto_a), step=0.05, key="man_a")
            
            senaryolar = ["Tümünü Sırala", "1/1", "1/0", "1/2", "0/1", "0/0", "0/2", "2/1", "2/0", "2/2"]
            hedef_iyms = st.selectbox("📌 Özellikle Görmek İstediğin Bir Senaryo Var Mı?", senaryolar)
            st.markdown("</div><br>", unsafe_allow_html=True)

            if st.button("🔍 GEÇMİŞ İY/MS İSTATİSTİKLERİNİ GETİR", use_container_width=True):
                with st.spinner(f"Son 4 yıldaki [{man_h} - {man_d} - {man_a}] oranlı maçlar taranıyor..."):
                    tolerans = 0.15
                    mask = (
                        (df_history['B365H'] >= man_h - tolerans) & (df_history['B365H'] <= man_h + tolerans) &
                        (df_history['B365A'] >= man_a - tolerans) & (df_history['B365A'] <= man_a + tolerans)
                    )
                    benzer_maclar = df_history[mask].copy()
                    benzer_maclar = benzer_maclar.dropna(subset=['HTR', 'FTR'])
                    toplam_benzer_mac = len(benzer_maclar)

                    if toplam_benzer_mac < 10:
                        st.warning(f"🚨 Geçmişte bu oran kalıbına sahip yeterli maç oynanmamış (Sadece {toplam_benzer_mac} maç bulundu). Sağlıklı bir istatistik verilemiyor.")
                    else:
                        st.success(f"✅ Geçmiş 4 yılda tam **{toplam_benzer_mac}** adet maç bu oran kalıbıyla oynanmış. İşte somut sonuçları:")
                        
                        ht_map = {'H': '1', 'D': '0', 'A': '2'}
                        ft_map = {'H': '1', 'D': '0', 'A': '2'}
                        benzer_maclar['IYMS_Kombinasyon'] = benzer_maclar['HTR'].map(ht_map) + "/" + benzer_maclar['FTR'].map(ft_map)
                        
                        sonuclar = benzer_maclar['IYMS_Kombinasyon'].value_counts().reset_index()
                        sonuclar.columns = ['İY / MS', 'Kaç Kere Geldi']
                        sonuclar['Gelme İhtimali (%)'] = (sonuclar['Kaç Kere Geldi'] / toplam_benzer_mac) * 100
                        sonuclar['Gelme İhtimali (%)'] = sonuclar['Gelme İhtimali (%)'].apply(lambda x: f"% {x:.1f}")

                        if hedef_iyms != "Tümünü Sırala":
                            hedef_veri = sonuclar[sonuclar['İY / MS'] == hedef_iyms]
                            if not hedef_veri.empty:
                                kac_kere = hedef_veri.iloc[0]['Kaç Kere Geldi']
                                yuzde = hedef_veri.iloc[0]['Gelme İhtimali (%)']
                                st.markdown(f"<div style='background:rgba(255,51,102,0.1); border:1px solid #ff3366; padding:15px; border-radius:8px; text-align:center; margin-bottom:20px;'><h3 style='margin:0; color:#ff3366;'>Senin Seçimin: {hedef_iyms}</h3><p style='margin-top:10px; font-size:18px;'>Geçmişte <b>{toplam_benzer_mac}</b> maçın <b>{kac_kere}</b> tanesinde senin hedefin gelmiş (<b>{yuzde}</b>).</p></div>", unsafe_allow_html=True)
                            else:
                                st.warning(f"Geçmişteki {toplam_benzer_mac} maçın HİÇBİRİ {hedef_iyms} olarak bitmemiş!")

                        st.markdown("### 🏆 En Çok Gelen İY/MS Liderlik Tablosu")
                        st.dataframe(sonuclar, use_container_width=True, hide_index=True)
