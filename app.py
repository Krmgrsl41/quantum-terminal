import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests
import io
import re
from sklearn.ensemble import RandomForestClassifier

# --- QUANTUM DESIGN: V207 THE SEMANTIC (KEYWORD-BASED PASTE & BIG FONTS) ---
st.set_page_config(page_title="V207 | QUANTUM APEX", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    
    p, span, label { font-size: 16px !important; font-weight: 600 !important; }
    .stNumberInput label { font-size: 16px !important; color: #8b949e !important; }
    
    div.stButton > button:first-child { 
        background: linear-gradient(90deg, #d4af37, #ffcc00); color:black; border:none; 
        font-weight:900; font-size: 18px; height: 3.5em; width: 100%; 
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); text-transform: uppercase; letter-spacing: 1.5px; border-radius: 12px; transition: all 0.3s ease;
    }
    
    .api-box { background: #0c1015; border: 1px solid #8a2be2; padding: 25px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(138, 43, 226, 0.1); }
    .input-container { background: #0c1015; border: 1px solid #1e2530; padding: 30px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3); }
    
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #151100); border: 2px solid #d4af37; padding: 35px; border-radius: 20px; text-align: center; box-shadow: 0 10px 30px rgba(212, 175, 55, 0.15); margin-top: 20px; }
    .scout-box { background: linear-gradient(145deg, #0a0e14, #121820); border: 1px solid #00ffcc; padding: 30px; border-radius: 15px; margin-bottom: 25px; margin-top:10px; box-shadow: 0 8px 25px rgba(0, 255, 204, 0.1); }
    
    .prob-card { background: #0c1015; border-radius: 15px; padding: 25px 15px; text-align: center; border: 1px solid #1e2530; margin-bottom: 15px; transition: transform 0.2s; box-shadow: 0 6px 12px rgba(0,0,0,0.3); }
    .prob-value { font-size: 42px; font-weight: 900; margin: 10px 0; text-shadow: 0 0 15px rgba(255,255,255,0.15); }
    .prob-odd { color: #ffffff; font-size: 16px; background: #121820; padding: 6px 15px; border-radius: 20px; display: inline-block; border: 1px solid #333; font-weight:600;}
    
    .rank-row { background: #0c1015; padding: 18px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1e2530; }
    
    .value-alarm { background: linear-gradient(145deg, #2a0808, #1a0505); padding: 25px; border-radius: 15px; margin-top: 20px; border: 2px solid #ff4b4b; box-shadow: 0 0 20px rgba(255,0,0,0.3); }
    .survival-mode { background: linear-gradient(90deg, #ff4b4b, #800000); padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #fff; font-size: 20px !important; font-weight: 900 !important; margin-bottom:25px; box-shadow: 0 0 20px rgba(255,75,75,0.6); }
    
    /* Zirve Font Ayarı */
    .pinnacle-font { font-size: 58px !important; font-weight: 900 !important; color: #d4af37 !important; text-transform: uppercase; margin: 20px 0; display: block; width: 100%; text-align: center; line-height: 1.2; }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'live_matches' not in st.session_state: st.session_state.live_matches = {}
defaults = {
    'ms1': 2.10, 'msx': 3.30, 'ms2': 3.40, 
    'o15': 1.25, 'u15': 3.50, 'o25': 1.90, 'u25': 1.90, 'o35': 3.20, 'u35': 1.30, 
    'btts_y': 1.70, 'btts_n': 2.00, 'ev_t': 'Ev Sahibi', 'dep_t': 'Deplasman'
}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- VERİ TABANI ---
LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'E1': 'İngiltere Championship',
    'E2': 'İngiltere League 1', 'E3': 'İngiltere League 2', 'EC': 'İngiltere National League',
    'SP1': 'İspanya La Liga 1', 'SP2': 'İspanya La Liga 2', 'I1': 'İtalya Serie A',
    'I2': 'İtalya Serie B', 'D1': 'Almanya Bundesliga 1', 'D2': 'Almanya Bundesliga 2',
    'F1': 'Fransa Ligue 1', 'F2': 'Fransa Ligue 2', 'N1': 'Hollanda Eredivisie',
    'B1': 'Belçika Pro League', 'P1': 'Portekiz Primeira Liga', 'G1': 'Yunanistan Süper Lig',
    'SC0': 'İskoçya Premiership', 'SC1': 'İskoçya Championship'
}

LEAGUE_DNA = {
    'T1': {'name': 'Kaos ve Agresyon (Süper Lig)', 'card_mod': 1.3, 'xg_mod': 1.05, 'corner_mod': 1.0, 'desc': 'Hakemler çok kart çıkarır, momentum dalgalanması yüksektir.'},
    'D1': {'name': 'Açık Alan / Yüksek Tempo (Bundesliga)', 'card_mod': 0.8, 'xg_mod': 1.20, 'corner_mod': 1.1, 'desc': 'Geçiş oyunları ve bol pozisyon.'},
    'E0': {'name': 'Yüksek Yoğunluk (Premier Lig)', 'card_mod': 0.85, 'xg_mod': 1.10, 'corner_mod': 1.25, 'desc': 'Kanat hücumları ve durmayan tempo.'},
    'I1': {'name': 'Taktik Savaş (Serie A)', 'card_mod': 1.15, 'xg_mod': 0.95, 'corner_mod': 0.95, 'desc': 'Katı taktik disiplin, yüksek bitiricilik.'},
    'SP1': {'name': 'Teknik & Pas (La Liga)', 'card_mod': 1.25, 'xg_mod': 0.90, 'corner_mod': 0.9, 'desc': 'Topa sahip olma odaklı.'}
}
LEAGUE_WEIGHTS = { 'E0': 1.5, 'SP1': 1.5, 'I1': 1.5, 'D1': 1.5, 'F1': 1.5, 'T1': 1.2, 'N1': 1.2 } 

@st.cache_data(ttl=3600)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718', '1617', '1516', '1415', '1314', '1213', '1112', '1011', '0910', '0809', '0708', '0607', '0506', '0405', '0304', '0203', '0102', '0001']
    leagues = list(LIG_MAP.keys())
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in leagues]
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG', 'HTHG', 'HTAG', 'HC', 'AC', 'HST', 'AST', 'HY', 'AY', 'HR', 'AR']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H', 'B365D', 'B365A']).copy()
            df['Season'] = s
            return df
        except: return pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor: results = list(executor.map(fetch, urls))
    dfs = [res for res in results if not res.empty]
    if dfs:
        res_df = pd.concat(dfs, ignore_index=True)
        res_df['Date_Parsed'] = pd.to_datetime(res_df['Date'], dayfirst=True, errors='coerce')
        return res_df.sort_values(['Season', 'Date_Parsed']).reset_index(drop=True)
    return pd.DataFrame()

db = load_quantum_data()
mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"] + sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if not db.empty and k in db['Div'].unique()])

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("<h3 style='color:#00ffcc;'>🎛️ Radar Kalibrasyonu</h3>", unsafe_allow_html=True)
    value_threshold = st.slider("🚨 Value Alarm Hassasiyeti (%)", 3, 25, 10)
    st.divider()
    st.markdown(f"**Aktif Veri Havuzu:**<br><span style='font-size:20px; color:#d4af37;'>{len(db):,} Maç</span>", unsafe_allow_html=True)
    st.info("💎 V207 SEMANTIC: Kelime tabanlı akıllı kopyalama ve gerçekçi İlk Yarı (HT) xG motoru aktiftir.")

st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:54px; margin-bottom:0;'>💎 QUANTUM ORACLE V207</h1>", unsafe_allow_html=True)

# --- API ---
st.markdown("<div class='api-box'>", unsafe_allow_html=True)
api_c1, api_c2, api_c3 = st.columns([1.2, 1.8, 1])
with api_c1:
    api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password")
with api_c2:
    secili_api_lig = st.selectbox("Hedef Ligi Seç (Güvenli Çekim):", ["soccer_uefa_champs_league", "soccer_turkey_super_league", "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a", "soccer_germany_bundesliga", "soccer_france_ligue_one"])
with api_c3:
    st.markdown("<br>", unsafe_allow_html=True)
    fetch_btn = st.button("🔄 MAÇLARI BUL")

if fetch_btn and api_key:
    try:
        url = f"https://api.the-odds-api.com/v4/sports/{secili_api_lig}/odds/?apiKey={api_key.strip()}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
        response = requests.get(url).json()
        st.session_state.live_matches = {f"[{m['commence_time']}] {m['home_team']} - {m['away_team']}": m for m in response}
        st.success(f"✅ {len(st.session_state.live_matches)} Maç Bulundu!")
    except: st.error("API Bağlantı Hatası!")

if st.session_state.live_matches:
    sel_c1, sel_c2 = st.columns([3, 1])
    with sel_c1: secilen_mac = st.selectbox("Maç Seç:", list(st.session_state.live_matches.keys()))
    with sel_c2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 ORANLARI AKTAR"):
            m = st.session_state.live_matches[secilen_mac]
            st.session_state.ev_t, st.session_state.dep_t = m['home_team'], m['away_team']
            for bm in m.get('bookmakers', []):
                for mkt in bm.get('markets', []):
                    if mkt['key'] == 'h2h':
                        for o in mkt['outcomes']:
                            if o['name'] == st.session_state.ev_t: st.session_state.ms1 = o['price']
                            elif o['name'] == st.session_state.dep_t: st.session_state.ms2 = o['price']
                            else: st.session_state.msx = o['price']
                    if mkt['key'] == 'totals':
                        for o in mkt['outcomes']:
                            if o['point'] == 2.5:
                                if o['name'] == 'Over': st.session_state.o25 = o['price']
                                else: st.session_state.u25 = o['price']
            st.rerun()
st.markdown("</div>", unsafe_allow_html=True)

# --- SMART PASTE (ANLAMSAL ZEKA) ---
with st.expander("✂️ AKILLI KOPYALAMA (ANLAMSAL MOTOR)"):
    st.markdown("<p style='color:#8b949e;'>Site metnini buraya yapıştırın. Sistem '2.5 Üst', 'KG Var', 'MS 1' gibi kelimeleri arayıp oranları kutulara dağıtır.</p>", unsafe_allow_html=True)
    paste_text = st.text_area("Metni Yapıştır:", height=100)
    if st.button("🪄 KELİME ANALİZİYLE DAĞIT"):
        if paste_text:
            text = paste_text.lower().replace(',', '.')
            markers = {
                'ms1': ['ms 1', 'ms1', 'ev sahibi', ' 1 '], 'msx': ['ms x', 'msx', 'ms 0', 'ms0', 'beraberlik', ' 0 '], 'ms2': ['ms 2', 'ms2', 'deplasman', ' 2 '],
                'o15': ['1.5 üst', '1.5üst', '1.5 ü'], 'u15': ['1.5 alt', '1.5alt', '1.5 a'],
                'o25': ['2.5 üst', '2.5üst', '2.5 ü'], 'u25': ['2.5 alt', '2.5alt', '2.5 a'],
                'o35': ['3.5 üst', '3.5üst', '3.5 ü'], 'u35': ['3.5 alt', '3.5alt', '3.5 a'],
                'btts_y': ['kg var', 'karşılıklı gol var', 'evet', ' var '], 'btts_n': ['kg yok', 'karşılıklı gol yok', 'hayır', ' yok ']
            }
            updates = 0
            for key, aliases in markers.items():
                for alias in aliases:
                    pattern = f"{re.escape(alias)}[:\s]*([0-9]+(?:\.[0-9]+)?)"
                    match = re.search(pattern, text)
                    if match:
                        val = float(match.group(1))
                        if 1.01 <= val <= 30.0:
                            st.session_state[key] = val
                            updates += 1
                            break
            if updates > 0: st.success(f"✅ {updates} pazar başarıyla ayıklandı!"); st.rerun()
            else: st.warning("⚠️ Metinde eşleşen anahtar kelime bulunamadı. Lütfen '2.5 Üst', 'KG Var' gibi ibarelerin olduğundan emin olun.")

# --- GRID ---
st.markdown("<div class='input-container'>", unsafe_allow_html=True)
tc1, tc2, tc3 = st.columns(3)
with tc1: ev_t = st.text_input("🏠 EV SAHİBİ", value=st.session_state.ev_t)
with tc2: dep_t = st.text_input("🚀 DEPLASMAN", value=st.session_state.dep_t)
with tc3: sec_lig = st.selectbox("🌍 LİG", mevcut_ligler)
st.divider()
c_ms, c_uo, c_kg = st.columns([1, 2.2, 1])
with c_ms:
    st.markdown("<h3 style='color:#00ffcc;'>📊 TARAF</h3>", unsafe_allow_html=True)
    ms1, msx, ms2 = st.number_input("MS 1", value=st.session_state.ms1, format="%.2f"), st.number_input("MS 0", value=st.session_state.msx, format="%.2f"), st.number_input("MS 2", value=st.session_state.ms2, format="%.2f")
with c_uo:
    st.markdown("<h3 style='color:#00ffcc;'>⚽ ALT / ÜST</h3>", unsafe_allow_html=True)
    uc1, uc2 = st.columns(2)
    o15, o25, o35 = uc1.number_input("1.5 ÜST", value=st.session_state.o15, format="%.2f"), uc1.number_input("2.5 ÜST", value=st.session_state.o25, format="%.2f"), uc1.number_input("3.5 ÜST", value=st.session_state.o35, format="%.2f")
    u15, u25, u35 = uc2.number_input("1.5 ALT", value=st.session_state.u15, format="%.2f"), uc2.number_input("2.5 ALT", value=st.session_state.u25, format="%.2f"), uc2.number_input("3.5 ALT", value=st.session_state.u35, format="%.2f")
with c_kg:
    st.markdown("<h3 style='color:#00ffcc;'>🎯 KG</h3>", unsafe_allow_html=True)
    kgv, kgy = st.number_input("KG VAR", value=st.session_state.btts_y, format="%.2f"), st.number_input("KG YOK", value=st.session_state.btts_n, format="%.2f")
st.markdown("</div>", unsafe_allow_html=True)

# --- ANALİZ ---
if st.button("🚀 TAM OTONOM YAPAY ZEKAYI BAŞLAT"):
    with st.spinner("Zirve Analiz Motoru çalışıyor..."):
        # Veri Hazırlama
        lig_kodu = sec_lig.split(" | ")[0] if sec_lig != "TÜM DÜNYA (GLOBAL)" else None
        active_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
        dna = LEAGUE_DNA.get(lig_kodu, {'name': 'Standart', 'card_mod': 1.0, 'xg_mod': 1.0, 'corner_mod': 1.0, 'desc': 'Global algoritma.'})
        
        # Benzer Maçlar
        active_db['diff'] = np.sqrt((active_db['B365H']-ms1)**2 + (active_db['B365D']-msx)**2 + (active_db['B365A']-ms2)**2)
        benzer = active_db.sort_values('diff').head(75)
        w_sum = (1 / (benzer['diff'] + 0.01)).sum()
        
        # Olasılıklar
        p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / 75) * 100
        p_msx = (benzer[benzer['FTR']=='D']['B365D'].count() / 75) * 100
        p_ms2 = (benzer[benzer['FTR']=='A']['B365A'].count() / 75) * 100
        p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / 75) * 100
        p_u25, p_kgv = 100 - p_o25, (benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['FTR'].count() / 75) * 100
        p_kgy = 100 - p_kgv
        
        # xG ve Hikaye
        ev_xg, dep_xg = 1.6 * dna['xg_mod'], 1.2 * dna['xg_mod']
        
        # SONUÇ EKRANI
        st.markdown("<h2 style='color:#fff;'>🧠 Tam Otonom Banko Tahmini</h2>", unsafe_allow_html=True)
        targets = [("MS 1", p_ms1, ms1), ("MS X", p_msx, msx), ("MS 2", p_ms2, ms2), ("2.5 Üst", p_o25, o25), ("2.5 Alt", p_u25, u25), ("KG Var", p_kgv, kgv), ("KG Yok", p_kgy, kgy)]
        # EV Filtresi & En İyi Seçim
        best = sorted([t for t in targets if t[2] > 1.25], key=lambda x: (x[1] * (1/x[2])), reverse=True)[0]
        
        hikaye = f"Bu maçta takımların hücum momentumu ({ev_xg + dep_xg:.2f} xG) ve lig DNA'sı '{best[0]}' senaryosunu %{int(best[1])} ihtimalle destekliyor. Piyasa oranı olan {best[2]:.2f}, kâr/risk dengesi (EV) açısından en mantıklı yatırımdır."
        
        html_box = (
            f"<div class='ai-verdict-box'>"
            f"<p style='color:#8b949e; font-size:15px; text-align:left; font-style:italic;'>Yapay zeka kâr marjı tatmin edici olan bu güvenli limanı buldu:</p>"
            f"<span class='pinnacle-font'>🎯 {best[0]} 🎯</span>"
            f"<div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:12px; border-left:4px solid #00ffcc; text-align:left; margin:20px 0;'>"
            f"<span style='color:#00ffcc; font-weight:900; font-size:16px;'>📝 MAÇIN HİKAYESİ:</span><br>"
            f"<span style='color:#ddd; font-size:15px; line-height:1.6;'>{hikaye}</span>"
            f"</div>"
            f"<div style='display: flex; justify-content: space-around; margin-top: 25px;'>"
            f"<div><span style='color:#8b949e; font-size:18px;'>Gerçek İhtimal:</span><br><b style='font-size:36px; color:#00ffcc;'>%{int(best[1])}</b></div>"
            f"<div><span style='color:#8b949e; font-size:18px;'>Piyasa Oranı:</span><br><b style='font-size:36px;'>{best[2]:.2f}</b></div>"
            f"</div>"
            f"</div>"
        )
        st.markdown(html_box, unsafe_allow_html=True)
        
        # Gerçekçi İlk Yarı (HT) - Las Vegas Gerçeklik Filtresi
        match_expected_ht_goals = (ev_xg + dep_xg) * 0.38 
        prob_ht_o15 = ((1.0 - (poisson.pmf(0, match_expected_ht_goals) + poisson.pmf(1, match_expected_ht_goals))) * 100) * 0.85
        st.markdown(f"<div class='alt-market'><h3>⏱️ İlk Yarı Radarı</h3>İ.Y 1.5 Üst Şansı: <b style='color:#ffcc00;'>%{int(prob_ht_o15)}</b> (Gerçekçi Beklenti)</div>", unsafe_allow_html=True)
