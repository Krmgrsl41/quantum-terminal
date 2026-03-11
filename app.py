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

# --- QUANTUM DESIGN: V201 THE MASTERMIND (FIXED POOL, REALISTIC xG & AI SYNTHESIS) ---
st.set_page_config(page_title="V201 | QUANTUM APEX", layout="wide", page_icon="👑")

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
    div.stButton > button:first-child:hover { transform: translateY(-3px); box-shadow: 0 8px 25px rgba(212, 175, 55, 0.7); }
    
    h1, h2, h3, h4 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .api-box { background: #0c1015; border: 1px solid #8a2be2; padding: 25px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(138, 43, 226, 0.1); }
    .input-container { background: #0c1015; border: 1px solid #1e2530; padding: 30px; border-radius: 15px; margin-bottom: 25px; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3); }
    
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #151100); border: 2px solid #d4af37; padding: 35px; border-radius: 20px; text-align: center; box-shadow: 0 10px 30px rgba(212, 175, 55, 0.15); margin-top: 20px; }
    .scout-box { background: linear-gradient(145deg, #0a0e14, #121820); border: 1px solid #00ffcc; padding: 30px; border-radius: 15px; margin-bottom: 25px; margin-top:10px; box-shadow: 0 8px 25px rgba(0, 255, 204, 0.1); }
    
    .prob-card { background: #0c1015; border-radius: 15px; padding: 25px 15px; text-align: center; border: 1px solid #1e2530; margin-bottom: 15px; transition: transform 0.2s; box-shadow: 0 6px 12px rgba(0,0,0,0.3); }
    .prob-card:hover { transform: translateY(-5px); box-shadow: 0 10px 20px rgba(0,0,0,0.5); }
    .prob-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px; }
    .prob-value { font-size: 42px; font-weight: 900; margin: 10px 0; text-shadow: 0 0 15px rgba(255,255,255,0.15); }
    .prob-odd { color: #ffffff; font-size: 16px; background: #121820; padding: 6px 15px; border-radius: 20px; display: inline-block; border: 1px solid #333; font-weight:600;}
    
    .rank-row { background: #0c1015; padding: 18px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1e2530; transition: all 0.2s; }
    .rank-row:hover { transform: scale(1.02); border-color: #d4af37; box-shadow: 0 5px 15px rgba(212, 175, 55, 0.1);}
    
    .team-form-container { display: flex; justify-content: space-between; font-size: 16px; align-items: center; }
    .badge-w, .badge-d, .badge-l { padding: 4px 10px; border-radius: 6px; font-weight: 800; margin: 0 3px; font-size: 14px;}
    .badge-w { background-color: rgba(0, 255, 204, 0.2); color: #00ffcc; border: 1px solid #00ffcc; }
    .badge-d { background-color: rgba(212, 175, 55, 0.2); color: #ffcc00; border: 1px solid #ffcc00; }
    .badge-l { background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b; border: 1px solid #ff4b4b; }
    
    .syndicate-badge { background: #1a1500; border: 1px solid #d4af37; color: #d4af37; padding: 5px 10px; border-radius: 6px; font-size: 13px; font-weight: 800; margin-right: 6px; display:inline-block; margin-bottom:8px;}
    
    .value-alarm { background: linear-gradient(90deg, #ff0000, #800000); padding: 25px; border-radius: 15px; margin-top: 20px; text-align: center; border: 2px solid #ff4b4b; box-shadow: 0 0 25px rgba(255,0,0,0.5); animation: pulse 2s infinite; }
    .trap-alarm { background: linear-gradient(90deg, #8a2be2, #4b0082); padding: 25px; border-radius: 15px; margin-top: 20px; text-align: center; border: 2px solid #d4af37; box-shadow: 0 0 25px rgba(138,43,226,0.5); }
    .survival-mode { background: linear-gradient(90deg, #ff4b4b, #800000); padding: 20px; border-radius: 15px; text-align: center; border: 2px solid #fff; font-size: 20px !important; font-weight: 900 !important; margin-bottom:25px; box-shadow: 0 0 20px rgba(255,75,75,0.6); animation: pulse 2s infinite; }
    
    @keyframes pulse { 0% { box-shadow: 0 0 15px rgba(255,0,0,0.5); } 50% { box-shadow: 0 0 35px rgba(255,0,0,0.8); } 100% { box-shadow: 0 0 15px rgba(255,0,0,0.5); } }
    
    .dna-box { background: #121820; padding: 20px; border-radius: 15px; border-left: 6px solid #8a2be2; margin-bottom: 20px; font-size: 16px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 4px 10px rgba(0,0,0,0.2);}
    .alt-market { background: #0c1015; padding: 25px; border-radius: 15px; border: 1px solid #1e2530; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.2); }
    .ml-box { background: linear-gradient(90deg, #0f2027, #203a43, #2c5364); padding: 25px; border-radius: 15px; border-left: 6px solid #00ffcc; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,255,204,0.15);}
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
default_vals = {
    'ms1': 2.10, 'msx': 3.30, 'ms2': 3.40, 
    'o15': 1.25, 'u15': 3.50, 'o25': 1.90, 'u25': 1.90, 'o35': 3.20, 'u35': 1.30, 
    'btts_y': 1.70, 'btts_n': 2.00, 'ev_t': 'Ev Sahibi', 'dep_t': 'Deplasman'
}
for k, v in default_vals.items():
    if k not in st.session_state: st.session_state[k] = v
if 'live_matches' not in st.session_state: st.session_state.live_matches = {}

# --- VERİ TABANI (FULL 25 YIL GERİ GELDİ) ---
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
    'D1': {'name': 'Açık Alan / Yüksek Tempo (Bundesliga)', 'card_mod': 0.8, 'xg_mod': 1.20, 'corner_mod': 1.1, 'desc': 'Geçiş oyunları ve bol pozisyon. 2.5 Üst ve KG VAR oranları yüksektir.'},
    'E0': {'name': 'Yüksek Yoğunluk (Premier Lig)', 'card_mod': 0.85, 'xg_mod': 1.10, 'corner_mod': 1.25, 'desc': 'Kanat hücumları ve durmayan tempo. Korner ve Gol beklentisi tavan yapar.'},
    'I1': {'name': 'Taktik Savaş (Serie A)', 'card_mod': 1.15, 'xg_mod': 0.95, 'corner_mod': 0.95, 'desc': 'Katı taktik disiplin, düşük şut yüzdesi ama yüksek bitiricilik.'},
    'SP1': {'name': 'Teknik & Pas (La Liga)', 'card_mod': 1.25, 'xg_mod': 0.90, 'corner_mod': 0.9, 'desc': 'Topa sahip olma odaklı. Düşük korner, yüksek hakem müdahalesi.'}
}
LEAGUE_WEIGHTS = { 'E0': 1.5, 'SP1': 1.5, 'I1': 1.5, 'D1': 1.5, 'F1': 1.5, 'T1': 1.2, 'N1': 1.2 } 

@st.cache_data(ttl=3600)
def load_quantum_data():
    # 26 BİN HATASI DÜZELTİLDİ: TÜM YILLAR GERİ EKLENDİ!
    seasons = [
        '2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718', '1617', 
        '1516', '1415', '1314', '1213', '1112', '1011', '0910', '0809', '0708', '0607', 
        '0506', '0405', '0304', '0203', '0102', '0001'
    ]
    leagues = list(LIG_MAP.keys())
    urls_to_fetch = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in leagues]
    
    def fetch_and_verify(item):
        s, l, url = item
        headers = { "User-Agent": "Mozilla/5.0" }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(response.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG', 'HTHG', 'HTAG', 'HC', 'AC', 'HST', 'AST', 'HY', 'AY', 'HR', 'AR']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H', 'B365D', 'B365A']).copy()
            df['Season'] = s
            return df
        except: return pd.DataFrame()

    dfs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        results = list(executor.map(fetch_and_verify, urls_to_fetch))
        
    if dfs := [res for res in results if not res.empty]:
        res_df = pd.concat(dfs, ignore_index=True)
        res_df['Date_Parsed'] = pd.to_datetime(res_df['Date'], dayfirst=True, errors='coerce')
        res_df = res_df.sort_values(['Season', 'Date_Parsed']).reset_index(drop=True)
        return res_df
    return pd.DataFrame()

db = load_quantum_data()
mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"]
if not db.empty and 'Div' in db.columns:
    mevcut_ligler += sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if k in db['Div'].unique()])
else:
    mevcut_ligler += sorted([f"{k} | {v}" for k, v in LIG_MAP.items()])

with st.sidebar:
    st.markdown("<h3 style='color:#00ffcc;'>🎛️ Radar Kalibrasyonu</h3>", unsafe_allow_html=True)
    value_threshold = st.slider("🚨 Value Alarm Hassasiyeti (%)", min_value=3, max_value=25, value=10, step=1)
    st.divider()
    st.markdown(f"<div style='background:#0c1015; padding:15px; border-radius:10px; border:1px solid #1e2530; font-size:16px;'><b>Aktif Veri Havuzu:</b><br><span style='font-size:20px; color:#d4af37;'>{len(db):,} Maç</span></div>", unsafe_allow_html=True)
    if len(db) == 0:
        st.markdown("<div style='background:rgba(255, 75, 75, 0.1); border:1px solid #ff4b4b; padding:15px; border-radius:10px; margin-top:15px;'><span style='color:#ff4b4b; font-size:15px; font-weight:bold;'>⚠️ Veri İndirme Başarısız!</span><br><span style='color:#8b949e; font-size:14px;'>Güvenlik duvarını aşmak için Hayalet Modu'nu kullanın.</span></div>", unsafe_allow_html=True)
        if st.button("🔄 Hayalet Modu ile Yeniden İndir"):
            st.cache_data.clear()
            st.rerun()
    st.divider()
    st.info("🧠 V201 THE MASTERMIND: Otonom Zeka Karar Motoru tüm verileri sentezleyecek şekilde yeniden yazıldı. İ.Y %44 xG limiti aktiftir.")

st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:54px; margin-bottom:0;'>👑 QUANTUM ORACLE V201</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#8b949e; font-size:18px; margin-top:5px;'>{datetime.datetime.now().strftime('%d.%m.%Y')} | The Mastermind: Yapay Zeka Sentez Motoru</p>", unsafe_allow_html=True)

st.markdown("<div class='api-box'>", unsafe_allow_html=True)
st.markdown("<h3 style='margin-top:0; color:#8a2be2;'>🛰️ Canlı Oran İstihbarat Merkezi (24s)</h3>", unsafe_allow_html=True)

api_c1, api_c2 = st.columns([2, 1])
with api_c1:
    gizli_api = st.secrets.get("API_KEY", "") if "API_KEY" in st.secrets else ""
    api_key = st.text_input("The-Odds-API Anahtarı (Bulut Kasasına Kilitli):", value=gizli_api, type="password")
with api_c2: fetch_btn = st.button("🔄 YAKLAŞAN MAÇLARI BUL")

if fetch_btn and api_key:
    with st.spinner("Küresel bahis borsaları taranıyor..."):
        try:
            clean_key = api_key.strip()
            target_leagues = ['soccer_turkey_super_league', 'soccer_epl', 'soccer_spain_la_liga', 'soccer_italy_serie_a', 'soccer_germany_bundesliga', 'soccer_france_ligue_one', 'soccer_uefa_champs_league', 'soccer_uefa_europa_league', 'soccer_netherlands_eredivisie']
            soccer_count = 0
            current_time_utc = datetime.datetime.now(datetime.timezone.utc)
            horizon_time_utc = current_time_utc + datetime.timedelta(hours=24)
            st.session_state.live_matches.clear()
            
            for league in target_leagues:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={clean_key}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
                response = requests.get(url)
                if response.status_code == 200:
                    for m in response.json():
                        try:
                            match_time_utc = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                            local_time = match_time_utc + datetime.timedelta(hours=3)
                            if current_time_utc < match_time_utc < horizon_time_utc:
                                time_str = local_time.strftime('%d.%m %H:%M')
                                baslik = f"[{time_str}] {m['home_team']} - {m['away_team']} | ({m.get('sport_title', 'Lig')})"
                                m['_sort_time'] = match_time_utc.timestamp()
                                m['_match_date'] = match_time_utc 
                                st.session_state.live_matches[baslik] = m
                                soccer_count += 1
                        except Exception: pass
            if soccer_count > 0: st.success(f"✅ {soccer_count} adet maç bulundu!")
            else: st.warning("⚠️ Seçili liglerde 24 saat içinde maç bulunamadı.")
        except Exception as e: st.error(f"❌ API Hatası: {str(e)}")

if st.session_state.live_matches:
    sel_c1, sel_c2 = st.columns([3, 1])
    with sel_c1:
        sorted_matches = sorted(list(st.session_state.live_matches.keys()), key=lambda x: st.session_state.live_matches[x]['_sort_time'])
        secilen_mac = st.selectbox("Analiz Edilecek Maçı Seçin:", ["Listeden Seçiniz..."] + sorted_matches)
    with sel_c2:
        if st.button("🚀 ORANLARI KUTULARA AKTAR"):
            if secilen_mac != "Listeden Seçiniz...":
                m_data = st.session_state.live_matches[secilen_mac]
                st.session_state.ev_t = m_data['home_team']
                st.session_state.dep_t = m_data['away_team']
                st.session_state.match_date_utc = m_data.get('_match_date', datetime.datetime.now(datetime.timezone.utc))
                ms1_list, msx_list, ms2_list = [], [], []
                o15_list, u15_list, o25_list, u25_list, o35_list, u35_list = [], [], [], [], [], []
                
                for bookmaker in m_data.get('bookmakers', []):
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'h2h':
                            for out in market.get('outcomes', []):
                                if out['name'] == st.session_state.ev_t: ms1_list.append(float(out['price']))
                                elif out['name'] == st.session_state.dep_t: ms2_list.append(float(out['price']))
                                elif out['name'] == 'Draw': msx_list.append(float(out['price']))
                        elif market['key'] == 'totals':
                            for out in market.get('outcomes', []):
                                pt = out.get('point')
                                if pt == 1.5:
                                    if out['name'] == 'Over': o15_list.append(float(out['price']))
                                    elif out['name'] == 'Under': u15_list.append(float(out['price']))
                                elif pt == 2.5:
                                    if out['name'] == 'Over': o25_list.append(float(out['price']))
                                    elif out['name'] == 'Under': u25_list.append(float(out['price']))
                                elif pt == 3.5:
                                    if out['name'] == 'Over': o35_list.append(float(out['price']))
                                    elif out['name'] == 'Under': u35_list.append(float(out['price']))
                
                if ms1_list: st.session_state.ms1 = round(sum(ms1_list)/len(ms1_list), 2)
                if msx_list: st.session_state.msx = round(sum(msx_list)/len(msx_list), 2)
                if ms2_list: st.session_state.ms2 = round(sum(ms2_list)/len(ms2_list), 2)
                if o15_list: st.session_state.o15 = round(sum(o15_list)/len(o15_list), 2)
                if u15_list: st.session_state.u15 = round(sum(u15_list)/len(u15_list), 2)
                if o25_list: st.session_state.o25 = round(sum(o25_list)/len(o25_list), 2)
                if u25_list: st.session_state.u25 = round(sum(u25_list)/len(u25_list), 2)
                if o35_list: st.session_state.o35 = round(sum(o35_list)/len(o35_list), 2)
                if u35_list: st.session_state.u35 = round(sum(u35_list)/len(u35_list), 2)
                st.rerun() 
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='input-container'>", unsafe_allow_html=True)
top_c1, top_c2, top_c3 = st.columns([1.5, 1.5, 1.5])
with top_c1: ev_t = st.text_input("🏠 EV SAHİBİ TAKIM", value=st.session_state.ev_t)
with top_c2: dep_t = st.text_input("🚀 DEPLASMAN TAKIM", value=st.session_state.dep_t)
with top_c3: sec_lig = st.selectbox("🌍 ANALİZ EDİLECEK LİG", mevcut_ligler)

st.markdown("<hr style='border-color: #1e2530; margin: 30px 0;'>", unsafe_allow_html=True)
col_ms, col_uo, col_kg = st.columns([1, 2.2, 1])

with col_ms:
    st.markdown("<h3 style='color:#00ffcc; text-align:center; margin-bottom:20px;'>📊 TARAF</h3>", unsafe_allow_html=True)
    ms1 = st.number_input("MS 1", value=st.session_state.ms1, format="%.2f")
    msx = st.number_input("MS X (0)", value=st.session_state.msx, format="%.2f")
    ms2 = st.number_input("MS 2", value=st.session_state.ms2, format="%.2f")

with col_uo:
    st.markdown("<h3 style='color:#00ffcc; text-align:center; margin-bottom:20px;'>⚽ ALT / ÜST</h3>", unsafe_allow_html=True)
    u_c1, u_c2 = st.columns(2)
    with u_c1:
        o15 = st.number_input("1.5 ÜST", value=st.session_state.o15, format="%.2f")
        o25 = st.number_input("2.5 ÜST", value=st.session_state.o25, format="%.2f")
        o35 = st.number_input("3.5 ÜST", value=st.session_state.o35, format="%.2f")
    with u_c2:
        u15 = st.number_input("1.5 ALT", value=st.session_state.u15, format="%.2f")
        u25 = st.number_input("2.5 ALT", value=st.session_state.u25, format="%.2f")
        u35 = st.number_input("3.5 ALT", value=st.session_state.u35, format="%.2f")

with col_kg:
    st.markdown("<h3 style='color:#00ffcc; text-align:center; margin-bottom:20px;'>🎯 KG DURUMU</h3>", unsafe_allow_html=True)
    kgv = st.number_input("KG VAR", value=st.session_state.btts_y, format="%.2f")
    kgy = st.number_input("KG YOK", value=st.session_state.btts_n, format="%.2f")
st.markdown("</div>", unsafe_allow_html=True)

def get_clean_team_name(team_name):
    name_map = str.maketrans("éáíóúüöçşğÉÁÍÓÚÜÖÇŞĞ", "eaiouuocsgeaiouuocsg")
    name = str(team_name).translate(name_map).lower().strip()
    aliases = {"atletico madrid": "Ath Madrid", "athletic bilbao": "Ath Bilbao", "tottenham": "Tottenham", "wolverhampton": "Wolves", "wolves": "Wolves", "manchester utd": "Man United", "manchester united": "Man United", "manchester city": "Man City", "nott'm forest": "Nott'm Forest", "nottingham": "Nott'm Forest", "paris sg": "Paris SG", "psg": "Paris SG", "bayern": "Bayern Munich", "leverkusen": "Leverkusen", "dortmund": "Dortmund", "m'gladbach": "M'gladbach", "inter": "Inter", "ac milan": "Milan", "roma": "Roma", "napoli": "Napoli", "juventus": "Juventus", "real madrid": "Real Madrid", "barcelona": "Barcelona", "galatasaray": "Galatasaray", "fenerbahce": "Fenerbahce"}
    for k, v in aliases.items():
        if k in name: return v
    clean_name = str(team_name).translate(name_map) 
    clean_name = re.sub(r'(?i)\s+(fc|bc|cf|united|utd|city|afc|fk|as|ac|sc|al|hotspur|albion|wanderers)$', '', clean_name).strip()
    return clean_name

def get_team_df(search_name, df):
    mask_home = df['HomeTeam'].str.contains(search_name, case=False, na=False, regex=False)
    mask_away = df['AwayTeam'].str.contains(search_name, case=False, na=False, regex=False)
    team_matches = df[mask_home | mask_away].copy()
    if team_matches.empty and len(search_name.split()) > 1:
        longest = max(search_name.split(), key=len)
        mask_home_l = df['HomeTeam'].str.contains(longest, case=False, na=False, regex=False)
        mask_away_l = df['AwayTeam'].str.contains(longest, case=False, na=False, regex=False)
        team_matches = df[mask_home_l | mask_away_l].copy()
        return team_matches, longest
    return team_matches, search_name

def get_syndicate_form(team_search_name, df, target_date_utc):
    team_matches, actual_search = get_team_df(team_search_name, df)
    if team_matches.empty: return 0, 0, 0, 0, 0, 0, 0, [], 0.0, "Bilinmiyor", "Normal", "Dengeli", 4.5, 1.5, 0.5
    team_matches['Date_Parsed'] = pd.to_datetime(team_matches['Date'], dayfirst=True, errors='coerce')
    team_matches = team_matches.dropna(subset=['Date_Parsed']).sort_values('Date_Parsed')
    last_5 = team_matches.tail(5)
    pts, gs, gc, games_played = 0, 0, 0, len(last_5)
    w, d, l, seq = 0, 0, 0, []
    elo_bonus, total_shots_on_target = 0.0, 0
    t_corners, t_cards, t_htg = [], [], []
    for _, row in last_5.iterrows():
        is_home = actual_search.lower() in str(row['HomeTeam']).lower()
        match_odds = row.get('B365H', 2.0) if is_home else row.get('B365A', 2.0)
        if is_home:
            gs += row.get('FTHG', 0); gc += row.get('FTAG', 0)
            total_shots_on_target += row.get('HST', row.get('FTHG', 0)*3) if pd.notna(row.get('HST')) else row.get('FTHG', 0)*3
            t_corners.append(row.get('HC', 4.5) if pd.notna(row.get('HC')) else 4.5)
            crd = row.get('HY', 1.5) + (row.get('HR', 0) * 2)
            t_cards.append(crd if pd.notna(crd) else 1.5)
            t_htg.append(row.get('HTHG', 0.5) if pd.notna(row.get('HTHG')) else 0.5)
            if row.get('FTR') == 'H': pts += 3; w += 1; seq.append('G'); elo_bonus += (match_odds * 0.5)
            elif row.get('FTR') == 'D': pts += 1; d += 1; seq.append('B'); elo_bonus += (match_odds * 0.1)
            else: l += 1; seq.append('M'); elo_bonus -= (1.0 / match_odds)
        else:
            gs += row.get('FTAG', 0); gc += row.get('FTHG', 0)
            total_shots_on_target += row.get('AST', row.get('FTAG', 0)*3) if pd.notna(row.get('AST')) else row.get('FTAG', 0)*3
            t_corners.append(row.get('AC', 4.5) if pd.notna(row.get('AC')) else 4.5)
            crd = row.get('AY', 1.5) + (row.get('AR', 0) * 2)
            t_cards.append(crd if pd.notna(crd) else 1.5)
            t_htg.append(row.get('HTAG', 0.5) if pd.notna(row.get('HTAG')) else 0.5)
            if row.get('FTR') == 'A': pts += 3; w += 1; seq.append('G'); elo_bonus += (match_odds * 0.5)
            elif row.get('FTR') == 'D': pts += 1; d += 1; seq.append('B'); elo_bonus += (match_odds * 0.1)
            else: l += 1; seq.append('M'); elo_bonus -= (1.0 / match_odds)
    last_match_date = last_5.iloc[-1]['Date_Parsed']
    target_dt = target_date_utc.replace(tzinfo=None) if target_date_utc else datetime.datetime.now()
    days_rest = (target_dt - last_match_date).days
    fatigue_status, fatigue_penalty = "Dinlenmiş", 0.0
    if 0 <= days_rest <= 3: fatigue_status, fatigue_penalty = "Yorgun ⚠️", -1.5
    elif days_rest > 10: fatigue_status, fatigue_penalty = "Maç Eksiği", -0.5
    elo_status = "Zorlu Rakipleri Geçti 🔥" if elo_bonus > 3.0 else ("Zayıflara Takıldı 📉" if elo_bonus < -1.0 else "Dengeli")
    expected_goals_from_shots = total_shots_on_target * 0.30 
    luck_status = "Aşırı Şanslı (Düşüş Beklenir) 🍀" if gs > expected_goals_from_shots + 2 else ("Şanssız (Patlama Yapabilir) 💣" if gs < expected_goals_from_shots - 2 else "Normal")
    final_momentum = ((pts / max(games_played, 1)) * 5 - 6) * 0.8 + (elo_bonus * 0.2) + fatigue_penalty
    return pts, gs, gc, games_played, w, d, l, seq, final_momentum, fatigue_status, elo_status, luck_status, np.nanmean(t_corners) if t_corners else 4.5, np.nanmean(t_cards) if t_cards else 1.5, np.nanmean(t_htg) if t_htg else 0.5

def get_color(prob): return "#00ffcc" if prob >= 60 else ("#ffcc00" if prob >= 40 else "#ff4b4b")

def build_seq_html(seq, align="left"):
    if not seq: return ""
    boxes = ""
    for res in seq:
        if res == 'G': boxes += "<span style='background:#00ffcc; color:#000; padding:4px 10px; border-radius:5px; font-weight:800; font-size:14px; margin-right:5px;'>G</span>"
        elif res == 'B': boxes += "<span style='background:#ffcc00; color:#000; padding:4px 10px; border-radius:5px; font-weight:800; font-size:14px; margin-right:5px;'>B</span>"
        elif res == 'M': boxes += "<span style='background:#ff4b4b; color:#fff; padding:4px 10px; border-radius:5px; font-weight:800; font-size:14px; margin-right:5px;'>M</span>"
    justify = "flex-start" if align == "left" else "flex-end"
    return f"<div style='margin-top:12px; display:flex; align-items:center; justify-content:{justify};'>{boxes}<span style='color:#8b949e; font-style:italic; font-size:14px; margin-left:6px;'>⬅️ Son Maç</span></div>"

@st.cache_resource(show_spinner=False)
def train_ml_model(df, lig_kodu):
    train_df = df if lig_kodu is None else df[df['Div'] == lig_kodu]
    features = ['B365H', 'B365D', 'B365A']
    train_df = train_df.dropna(subset=features + ['FTR']).tail(2000) 
    if len(train_df) < 50: return None
    X, y = train_df[features], train_df['FTR']
    rf = RandomForestClassifier(n_estimators=100, random_state=42, max_depth=5)
    rf.fit(X, y)
    return rf

if st.button("🚀 TAM OTONOM YAPAY ZEKAYI BAŞLAT"):
    aktif_db = db.copy()
    target_dt = st.session_state.get('match_date_utc', datetime.datetime.now(datetime.timezone.utc))
    
    if len(aktif_db) == 0 or 'Div' not in aktif_db.columns:
        st.error("❌ Veritabanı bozuk veya boş! Lütfen sol menüdeki '🔄 Hayalet Modu ile Yeniden İndir' butonuna basın.")
    else:
        for col in ['B365O', 'B365U', 'HTHG', 'HTAG']:
            if col not in aktif_db.columns: aktif_db[col] = np.nan
        lig_kodu = sec_lig.split(" | ")[0] if sec_lig != "TÜM DÜNYA (GLOBAL)" else None
        if lig_kodu: aktif_db = aktif_db[aktif_db['Div'] == lig_kodu]
        dna = LEAGUE_DNA.get(lig_kodu, {'name': 'Standart Mod', 'card_mod': 1.0, 'xg_mod': 1.0, 'corner_mod': 1.0, 'desc': 'Kültürel DNA saptanamadı, global algoritmalar devrede.'})

        ev_search_name, dep_search_name = get_clean_team_name(ev_t), get_clean_team_name(dep_t)
        ev_gecmis, act_ev = get_team_df(ev_search_name, aktif_db)
        dep_gecmis, act_dep = get_team_df(dep_search_name, aktif_db)

        with st.spinner("V201 MASTERMIND devrede: Sentez Motoru çalışıyor..."):
            is_survival, survival_boost = False, 1.0
            def get_ppg(team_name, param_df):
                m = param_df[(param_df['HomeTeam'].str.contains(team_name, case=False, na=False)) | (param_df['AwayTeam'].str.contains(team_name, case=False, na=False))]
                if len(m) < 5: return 1.5 
                pts = 0
                for _, r in m.iterrows():
                    is_h = team_name.lower() in str(r['HomeTeam']).lower()
                    if (is_h and r['FTR']=='H') or (not is_h and r['FTR']=='A'): pts += 3
                    elif r['FTR']=='D': pts += 1
                return pts / len(m)

            ev_ppg, dep_ppg = get_ppg(act_ev, aktif_db), get_ppg(act_dep, aktif_db)
            if datetime.datetime.now().month in [3, 4, 5]:
                if (ev_ppg < 1.0 and dep_ppg > 1.8) or (dep_ppg < 1.0 and ev_ppg > 1.8):
                    is_survival, survival_boost = True, 1.25 
                    
            if is_survival:
                st.markdown(f"<div class='survival-mode'>🚨 SURVIVAL MODE AKTİF: Düşme potasındaki takımın can havli motivasyonu ({survival_boost}x) xG algoritmalarına eklendi!</div>", unsafe_allow_html=True)
            
            rf_model = train_ml_model(aktif_db, lig_kodu)
            ml_preds = {'H': 0, 'D': 0, 'A': 0}
            if rf_model:
                probs = rf_model.predict_proba([[ms1, msx, ms2]])[0]
                for idx, c in enumerate(rf_model.classes_): ml_preds[c] = probs[idx] * 100

            ev_home_matches = ev_gecmis[ev_gecmis['HomeTeam'].str.contains(act_ev, case=False, na=False)].tail(5)
            dep_away_matches = dep_gecmis[dep_gecmis['AwayTeam'].str.contains(act_dep, case=False, na=False)].tail(5)
            
            ev_scored_home = ev_home_matches['FTHG'].mean() if not ev_home_matches.empty else 1.5
            ev_conceded_home = ev_home_matches['FTAG'].mean() if not ev_home_matches.empty else 1.0
            dep_scored_away = dep_away_matches['FTAG'].mean() if not dep_away_matches.empty else 1.1
            dep_conceded_away = dep_away_matches['FTHG'].mean() if not dep_away_matches.empty else 1.5
            
            true_ev_xg = ((ev_scored_home + dep_conceded_away) / 2) * dna['xg_mod'] * (survival_boost if ev_ppg < dep_ppg else 1.0)
            true_dep_xg = ((dep_scored_away + ev_conceded_home) / 2) * dna['xg_mod'] * (survival_boost if dep_ppg < ev_ppg else 1.0)

            h2h_mask = ((aktif_db['HomeTeam'].str.contains(act_ev, case=False, na=False) & aktif_db['AwayTeam'].str.contains(act_dep, case=False, na=False)) | (aktif_db['HomeTeam'].str.contains(act_dep, case=False, na=False) & aktif_db['AwayTeam'].str.contains(act_ev, case=False, na=False)))
            h2h_df = aktif_db[h2h_mask].dropna(subset=['Date']).tail(5)
            
            ev_h2h_pts, dep_h2h_pts = 0, 0
            if not h2h_df.empty:
                for _, row in h2h_df.iterrows():
                    if act_ev.lower() in str(row['HomeTeam']).lower():
                        if row['FTR'] == 'H': ev_h2h_pts += 3
                        elif row['FTR'] == 'A': dep_h2h_pts += 3
                    else:
                        if row['FTR'] == 'A': ev_h2h_pts += 3
                        elif row['FTR'] == 'H': dep_h2h_pts += 3
                h2h_advantage = (ev_h2h_pts - dep_h2h_pts) / (len(h2h_df) * 3) 
            else: h2h_advantage = 0.0

            ev_res = get_syndicate_form(ev_search_name, db, target_dt)
            dep_res = get_syndicate_form(dep_search_name, db, target_dt)
            ev_pts, ev_gs, ev_gc, ev_gp, ev_w, ev_d, ev_l, ev_seq, ev_momentum, ev_fatigue, ev_elo, ev_luck, ev_corn, ev_card, ev_htg = ev_res
            dep_pts, dep_gs, dep_gc, dep_gp, dep_w, dep_d, dep_l, dep_seq, dep_momentum, dep_fatigue, dep_elo, dep_luck, dep_corn, dep_card, dep_htg = dep_res
            
            match_expected_corners = (ev_corn + dep_corn) * dna['corner_mod']
            match_expected_cards = (ev_card + dep_card) * dna['card_mod']
            
            ev_xg = max(0.1, true_ev_xg + (ev_momentum * 0.05))
            dep_xg = max(0.1, true_dep_xg + (dep_momentum * 0.05))

            hassasiyet = 0.05
            while hassasiyet <= 0.40:
                aktif_db['diff'] = np.sqrt((aktif_db['B365H']-ms1)**2 + (aktif_db['B365D']-msx)**2 + (aktif_db['B365A']-ms2)**2)
                benzer = aktif_db[aktif_db['diff'] <= hassasiyet].sort_values('diff')
                if len(benzer) >= 20: break
                hassasiyet += 0.05

        if len(benzer) >= 10:
            benzer = benzer.head(75) 
            season_weights = {'2526': 2.0, '2425': 1.8, '2324': 1.6, '2223': 1.4, '2122': 1.2, '2021': 1.0, '1920': 0.8, '1819': 0.7}
            benzer['s_weight'] = benzer['Season'].map(season_weights).fillna(0.1)
            benzer['l_weight'] = benzer['Div'].map(LEAGUE_WEIGHTS).fillna(0.8) if lig_kodu is None else 1.0 
            benzer['weight'] = (1 / (benzer['diff'] + 0.01)) * benzer['s_weight'] * benzer['l_weight']
            w_sum = benzer['weight'].sum()

            avg_hist_ms1, avg_hist_ms2 = benzer['B365H'].mean(), benzer['B365A'].mean()
            anomaly_alert, anomaly_type = None, None
            
            if ms1 < (avg_hist_ms1 * 0.80): anomaly_alert, anomaly_type = f"⚠️ TUZAK UYARISI: {ev_t} oranı tarihsel ortalamanın çok altında! (Tarihsel: {avg_hist_ms1:.2f} -> Güncel: {ms1:.2f}).", "trap"
            elif ms2 < (avg_hist_ms2 * 0.80): anomaly_alert, anomaly_type = f"⚠️ TUZAK UYARISI: {dep_t} oranı tarihsel ortalamanın çok altında! (Tarihsel: {avg_hist_ms2:.2f} -> Güncel: {ms2:.2f}).", "trap"
            elif ms1 > (avg_hist_ms1 * 1.25): anomaly_alert, anomaly_type = f"💎 GİZLİ DEĞER: {ev_t} oranı tarihsel ortalamanın çok üzerinde! Piyasada sürü psikolojisi var!", "value"
            elif ms2 > (avg_hist_ms2 * 1.25): anomaly_alert, anomaly_type = f"💎 GİZLİ DEĞER: {dep_t} oranı tarihsel ortalamanın çok üzerinde! Piyasada sürü psikolojisi var!", "value"

            raw_p_ms1 = (benzer[benzer['FTR']=='H']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            raw_p_msx = (benzer[benzer['FTR']=='D']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            raw_p_ms2 = (benzer[benzer['FTR']=='A']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            
            raw_p_o15 = min(99.0, ((benzer[(benzer['FTHG']+benzer['FTAG'])>1.5]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            raw_p_o25 = min(99.0, ((benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            raw_p_o35 = min(99.0, ((benzer[(benzer['FTHG']+benzer['FTAG'])>3.5]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            
            raw_p_a15 = 100 - raw_p_o15 if raw_p_o15 > 0 else 0
            raw_p_a25 = 100 - raw_p_o25 if raw_p_o25 > 0 else 0
            raw_p_a35 = 100 - raw_p_o35 if raw_p_o35 > 0 else 0
            
            raw_p_kgv = min(99.0, ((benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            raw_p_kgy = 100 - raw_p_kgv if raw_p_kgv > 0 else 0

            ev_sapma = (ev_momentum * 1.5) + (h2h_advantage * 3.0)
            dep_sapma = (dep_momentum * 1.5) - (h2h_advantage * 3.0)
            
            p_ms1 = max(0.1, raw_p_ms1 + ev_sapma - (dep_sapma * 0.5))
            p_ms2 = max(0.1, raw_p_ms2 + dep_sapma - (ev_sapma * 0.5))
            p_msx = max(0.1, 100 - (p_ms1 + p_ms2)) 
            
            toplam_ms = p_ms1 + p_msx + p_ms2
            p_ms1 = (p_ms1 / toplam_ms) * 100; p_msx = (p_msx / toplam_ms) * 100; p_ms2 = (p_ms2 / toplam_ms) * 100
            
            xg_sum_diff = (true_ev_xg + true_dep_xg) - 2.5
            p_o15 = min(99.0, max(1.0, raw_p_o15 + (ev_momentum + dep_momentum)*0.2 + (xg_sum_diff * 4.0)))
            p_o25 = min(99.0, max(1.0, raw_p_o25 + (ev_momentum + dep_momentum)*0.5 + (xg_sum_diff * 6.0)))
            p_o35 = min(99.0, max(1.0, raw_p_o35 + (ev_momentum + dep_momentum)*0.7 + (xg_sum_diff * 8.0)))
            p_u15, p_u25, p_u35 = 100 - p_o15, 100 - p_o25, 100 - p_o35
            p_kgv = min(99.0, max(1.0, raw_p_kgv + (ev_momentum + dep_momentum)*0.5 + (xg_sum_diff * 4.0)))
            p_kgy = 100 - p_kgv

            ev_color = "#00ffcc" if ev_momentum > 0 else "#ff4b4b"
            dep_color = "#00ffcc" if dep_momentum > 0 else "#ff4b4b"
            
            st.markdown(f"""
            <div class='dna-box'>
                <div>
                    <span style='color:#d4af37; font-weight:900; font-size:18px;'>🧬 LİG DNA'SI: {dna['name']}</span><br>
                    <span style='color:#8b949e; font-size:16px;'>{dna['desc']}</span>
                </div>
                <div style='text-align:right;'>
                    <span class='syndicate-badge'>Kart Çarpanı: {dna['card_mod']}x</span>
                    <span class='syndicate-badge'>xG Çarpanı: {dna['xg_mod']}x</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

            form_radar_html = (
                f"<div class='scout-box'>"
                f"<div style='display:flex; align-items:center; margin-bottom:20px; border-bottom:1px solid #1e2530; padding-bottom:15px;'>"
                f"<span style='font-size:24px; margin-right:12px;'>📡</span>"
                f"<h3 style='color:#00ffcc; margin:0;'>PRO Form Radarı (Son {max(ev_gp, dep_gp, 5)} Maç İstatistiği)</h3>"
                f"</div>"
                f"<div class='team-form-container'>"
                f"<div style='flex:1; padding-right:15px;'>"
                f"<div style='font-size:22px; font-weight:900; color:#ffffff; margin-bottom:10px;'>🔵 {ev_t} (Ev)</div>"
                f"<div style='margin-bottom:12px;'><span class='badge-w'>{ev_w}G</span><span class='badge-d'>{ev_d}B</span><span class='badge-l'>{ev_l}M</span></div>"
                f"<div style='color:#8b949e; font-size:16px; line-height:1.8; margin-bottom:15px;'>"
                f"Toplanan Puan: <span style='color:#fff; font-weight:bold;'>{ev_pts}</span><br>Gol (A/Y): <span style='color:#00ffcc; font-weight:bold;'>{ev_gs}</span> - <span style='color:#ff4b4b; font-weight:bold;'>{ev_gc}</span><br>Momentum İvmesi: <span style='color: {ev_color}; font-weight:900; font-size:18px;'>{ev_momentum:.1f}</span>"
                f"</div>"
                f"<div><span class='syndicate-badge'>Zorluk: {ev_elo}</span><span class='syndicate-badge'>Durum: {ev_fatigue}</span><span class='syndicate-badge'>Bitiricilik: {ev_luck}</span></div>"
                f"{build_seq_html(ev_seq, 'left')}"
                f"</div>"
                f"<div style='width:2px; background-color:#1e2530; margin:0 20px;'></div>"
                f"<div style='flex:1; padding-left:15px; text-align:right;'>"
                f"<div style='font-size:22px; font-weight:900; color:#ffffff; margin-bottom:10px;'>🔴 {dep_t} (Dep)</div>"
                f"<div style='margin-bottom:12px;'><span class='badge-w'>{dep_w}G</span><span class='badge-d'>{dep_d}B</span><span class='badge-l'>{dep_l}M</span></div>"
                f"<div style='color:#8b949e; font-size:16px; line-height:1.8; margin-bottom:15px;'>"
                f"<span style='color:#fff; font-weight:bold;'>{dep_pts}</span> :Toplanan Puan<br><span style='color:#00ffcc; font-weight:bold;'>{dep_gs}</span> - <span style='color:#ff4b4b; font-weight:bold;'>{dep_gc}</span> :(A/Y) Gol<br><span style='color: {dep_color}; font-weight:900; font-size:18px;'>{dep_momentum:.1f}</span> :Momentum İvmesi"
                f"</div>"
                f"<div><span class='syndicate-badge'>Zorluk: {dep_elo}</span><span class='syndicate-badge'>Durum: {dep_fatigue}</span><span class='syndicate-badge'>Bitiricilik: {dep_luck}</span></div>"
                f"{build_seq_html(dep_seq, 'right')}"
                f"</div>"
                f"</div>"
                f"</div>"
            )
            st.markdown(form_radar_html, unsafe_allow_html=True)
            
            st.markdown("<h2 style='margin-bottom:20px; color:#ffffff;'>📊 Taraf & Skor İhtimalleri</h2>", unsafe_allow_html=True)
            r1_c1, r1_c2, r1_c3 = st.columns(3)
            r1_c1.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_ms1)};'><div class='prob-title'>{ev_t}</div><div class='prob-value' style='color:{get_color(p_ms1)};'>%{int(p_ms1)}</div><div class='prob-odd'>Oran: {ms1}</div></div>", unsafe_allow_html=True)
            r1_c2.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_msx)};'><div class='prob-title'>Beraberlik (0)</div><div class='prob-value' style='color:{get_color(p_msx)};'>%{int(p_msx)}</div><div class='prob-odd'>Oran: {msx}</div></div>", unsafe_allow_html=True)
            r1_c3.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_ms2)};'><div class='prob-title'>{dep_t}</div><div class='prob-value' style='color:{get_color(p_ms2)};'>%{int(p_ms2)}</div><div class='prob-odd'>Oran: {ms2}</div></div>", unsafe_allow_html=True)

            r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
            r2_c1.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_o25)};'><div class='prob-title'>2.5 ÜST</div><div class='prob-value' style='color:{get_color(p_o25)};'>%{int(p_o25)}</div><div class='prob-odd'>Oran: {o25}</div></div>", unsafe_allow_html=True)
            r2_c2.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_u25)};'><div class='prob-title'>2.5 ALT</div><div class='prob-value' style='color:{get_color(p_u25)};'>%{int(p_u25)}</div><div class='prob-odd'>Oran: {u25}</div></div>", unsafe_allow_html=True)
            r2_c3.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_kgv)};'><div class='prob-title'>KG VAR</div><div class='prob-value' style='color:{get_color(p_kgv)};'>%{int(p_kgv)}</div><div class='prob-odd'>Oran: {kgv}</div></div>", unsafe_allow_html=True)
            r2_c4.markdown(f"<div class='prob-card' style='border-top: 5px solid {get_color(p_kgy)};'><div class='prob-title'>KG YOK</div><div class='prob-value' style='color:{get_color(p_kgy)};'>%{int(p_kgy)}</div><div class='prob-odd'>Oran: {kgy}</div></div>", unsafe_allow_html=True)

            st.divider()
            
            targets = [
                ("MS 1", p_ms1, ms1), ("MS X", p_msx, msx), ("MS 2", p_ms2, ms2), 
                ("1.5 Üst", p_o15, o15), ("1.5 Alt", p_u15, u15),
                ("2.5 Üst", p_o25, o25), ("2.5 Alt", p_u25, u25),
                ("3.5 Üst", p_o35, o35), ("3.5 Alt", p_u35, u35),
                ("KG Var", p_kgv, kgv), ("KG Yok", p_kgy, kgy)
            ]

            det_l, det_r = st.columns(2)
            with det_l:
               st.markdown("<h2 style='color:#fff;'>🧠 Tam Otonom Banko Tahmini</h2>", unsafe_allow_html=True)
                
                # --- 3. YENİ YAPAY ZEKA GÜVEN VE SENTEZ MOTORU (DENGELİ KAR MARJI) ---
                ai_candidates = []
                for t_name, t_prob, t_odd in targets:
                    # FİLTRE: 1.25 ve altındaki oranlar kârlı yatırım değildir, yapay zeka bunları ana banko yapmaktan kaçınır.
                    if t_odd <= 1.25: continue 
                    
                    risk_mod = 1.0
                    if "1.5" in t_name: risk_mod = 1.15
                    elif "2.5" in t_name or "KG" in t_name: risk_mod = 1.05
                    elif "MS" in t_name: risk_mod = 0.85 
                    
                    implied_prob = (1 / t_odd) * 100
                    
                    # YENİ DENGE: Beklenen Değer (Expected Value - EV)
                    expected_value = (t_prob / 100) * t_odd
                    # Sadece ihtimale değil, kâr marjına da (EV) odaklanan yeni formül
                    guven_skoru = (t_prob * risk_mod) * expected_value
                    
                    ai_candidates.append((t_name, t_prob, t_odd, guven_skoru, implied_prob))

                if not ai_candidates: # Eğer bültende her şey 1.25 altındaysa mecburen en iyiyi al
                    ai_candidates.append((targets[0][0], targets[0][1], targets[0][2], 0, 100))

                ai_candidates.sort(key=lambda x: x[3], reverse=True)
                best_target = ai_candidates[0]
                name, prob, odd, _, imp_p = best_target

                # --- 4. DİNAMİK MAÇ HİKAYESİ OLUŞTURUCU ---
                hikaye = ""
                if "Üst" in name or "KG Var" in name:
                    hikaye = f"Bu maçta hücum hatları savunmalara göre ağır basıyor (Toplam Beklenen Gol: {(ev_xg+dep_xg):.2f}). Şirketler oranı {odd:.2f} seviyesinde tutarak riski dengelemeye çalışmış ancak istatistikler ve momentum maçın {name} senaryosuna gideceğini gösteriyor. Kâr/Risk dengesi açısından en optimal yatırım budur."
                elif "Alt" in name or "KG Yok" in name:
                    hikaye = f"Kısır bir mücadele bekleniyor. Savunma kurguları ve takım DNA'ları maçın temposunu düşürecektir. {odd:.2f} oranlık {name} tercihi, bu taktik savaşında paranızı korumak için en kârlı sığınaktır."
                elif "MS 1" in name:
                    hikaye = f"Ev sahibi avantajı, {ev_momentum:.1f} puanlık momentum ivmesi ve {ev_xg:.2f} xG (Gol Beklentisi) ile ibreyi tamamen kendine çevirmiş durumda. {odd:.2f} oran, bu senaryo için sistemdeki en değerli (Value) tercihtir."
                elif "MS 2" in name:
                    hikaye = f"Deplasman ekibi zorlu bir fikstürde olmasına rağmen {dep_xg:.2f} gol beklentisi ve dominant formuyla ağır basıyor. Şirketler deplasman faktörü yüzünden oranı ({odd:.2f}) yüksek tutarak tuzak kurmuş olabilir, veri bilimi tamamen Deplasman galibiyetini işaret ediyor."
                else:
                    hikaye = f"İki takımın da sahadaki momentumu ve ELO güçleri kilitlenmiş durumda. Matematiksel olarak en çok değer barındıran (Value) ve mantıklı tercih {name} olacaktır."

                if is_survival:
                    hikaye += " Ayrıca ligin sonlarındayız ve düşme hattında yaşanan 'Can Havli (Survival)' motivasyonu sahadaki mücadeleyi ve bu tercihi ekstra destekliyor."

                st.markdown(f"""
                <div class='ai-verdict-box'>
                    <p style='color:#8b949e; font-size:15px; text-align:left; font-style:italic;'>Yapay zeka salt kazanma ihtimallerini değil; pazar riskini ve oran değerlerini (EV) sentezleyerek seni kâr marjı tatmin edici olan bu limana yönlendirdi:</p>
                    <h1 style='color:#d4af37; font-size: 54px; font-weight:900; margin: 15px 0;'>🎯 {name} 🎯</h1>
                    
                    <div style='background:rgba(255,255,255,0.05); padding:20px; border-radius:12px; border-left:4px solid #00ffcc; text-align:left; margin:20px 0;'>
                        <span style='color:#00ffcc; font-weight:900; font-size:16px;'>📝 MAÇIN HİKAYESİ & ANALİZİ:</span><br>
                        <span style='color:#ddd; font-size:15px; line-height:1.6;'>{hikaye}</span>
                    </div>

                    <div style='display: flex; justify-content: space-around; margin-top: 25px;'>
                        <div><span style='color:#8b949e; font-size:18px;'>Gerçek İhtimal:</span><br><b style='font-size:36px; color:#00ffcc;'>%{int(prob)}</b></div>
                        <div><span style='color:#8b949e; font-size:18px;'>Piyasa Oranı:</span><br><b style='font-size:36px;'>{odd:.2f}</b></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                value_alarms = []
                for t in targets:
                    t_name, t_prob, t_odd = t
                    if t_odd > 1.05:
                        implied_prob = (1 / t_odd) * 100
                        if (t_prob - implied_prob) >= value_threshold: 
                            value_alarms.append(f"🔥 <span style='font-size:18px;'><b>{t_name}</b> (Açılan Oran: {t_odd:.2f})</span><br><span style='font-size:14px; font-weight:normal; color:#fff;'>Bahis şirketi bu sonuca sadece <b>%{int(implied_prob)}</b> ihtimal vererek oranı şişirmiş. Ancak yapay zekamız maçın dinamiklerinde bu ihtimalin <b>%{int(t_prob)}</b> olduğunu tespit etti. Bu <b>%{int(t_prob - implied_prob)}</b> oranında devasa bir hata ve değer (Value) fırsatıdır!</span>")
                
                if value_alarms:
                    alarm_text = "<br><hr style='border-color:#555; margin:10px 0;'><br>".join(value_alarms)
                    st.markdown(f"""
                    <div class='value-alarm' style='text-align:left;'>
                        <h2 style='margin:0 0 10px 0; color:#fff; font-weight:900; text-align:center;'>🚨 SİSTEM AÇIĞI (VALUE) TESPİT EDİLDİ!</h2>
                        <p style='font-size:15px; color:#ddd; margin-bottom:15px; text-align:center;'>Aşağıdaki seçeneklerde bahis şirketinin matematiksel hesaplama hatası tespit edilmiştir. Bu oranlara yatırım yapmak uzun vadeli kasanızı büyütür:</p>
                        <div style='background:rgba(0,0,0,0.3); padding:20px; border-radius:10px; border-left:5px solid #ffcc00;'>
                            {alarm_text}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                if anomaly_alert:
                    bg_class = 'trap-alarm' if anomaly_type == 'trap' else 'value-alarm'
                    st.markdown(f"<div class='{bg_class}'><span style='font-size:18px; font-weight:bold; color:#fff;'>{anomaly_alert}</span></div>", unsafe_allow_html=True)

                st.divider()
                st.markdown("<h3>🏆 İhtimal Hiyerarşisi (Tüm Pazarlar)</h3>", unsafe_allow_html=True)
                sirali_ihtimaller = sorted(targets, key=lambda x: x[1], reverse=True)
                for i, (isim, i_prob, i_odd) in enumerate(sirali_ihtimaller[:7]):
                    renk = "#00ffcc" if i_prob >= 60 else ("#d4af37" if i_prob >= 40 else "#ff4b4b")
                    st.markdown(f"<div class='rank-row' style='border-left: 6px solid {renk};'><span style='font-size: 18px;'><b>{i+1}.</b> {isim}</span><span style='color:{renk}; font-weight:900; font-size:24px;'>%{int(i_prob)}</span></div>", unsafe_allow_html=True)

            with det_r:
                st.markdown("<h2>📈 Dinamik Skor Matrisi (Dixon-Coles)</h2>", unsafe_allow_html=True)
                score_probs = {}
                rho = -0.15 
                for h in range(5):
                    for a in range(5):
                        base_prob = poisson.pmf(h, ev_xg) * poisson.pmf(a, dep_xg)
                        tau = 1.0
                        if h == 0 and a == 0: tau = max(0, 1 - (ev_xg * dep_xg * rho))
                        elif h == 1 and a == 0: tau = max(0, 1 + (dep_xg * rho))
                        elif h == 0 and a == 1: tau = max(0, 1 + (ev_xg * rho))
                        elif h == 1 and a == 1: tau = max(0, 1 - rho)
                        score_probs[f"{h} - {a}"] = base_prob * tau * 100
                        
                sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:6]
                chart_data = pd.DataFrame({"Skorlar": [f"{i+1}. İhtimal ({s[0]})" for i, s in enumerate(sorted_scores)], "İhtimal (%)": [int(s[1]) for s in sorted_scores]}).set_index("Skorlar")
                st.bar_chart(chart_data, color="#d4af37", height=250)
                
                # --- 2. GERÇEKÇİ İLK YARI (HT) xG FİLTRESİ ---
                # İstatistiksel gerçek: İlk yarıda toplam maç xG'sinin ortalama %44'ü gerçekleşir.
                match_expected_ht_goals = (ev_xg + dep_xg) * 0.44 
                prob_ht_0 = poisson.pmf(0, match_expected_ht_goals)
                prob_ht_1 = poisson.pmf(1, match_expected_ht_goals)
                prob_ht_o15 = (1.0 - (prob_ht_0 + prob_ht_1)) * 100
                
                ht_o15_color = "#00ffcc" if prob_ht_o15 >= 35 else ("#ffcc00" if prob_ht_o15 >= 25 else "#ff4b4b")
                ht_text = "İ.Y 1.5 ÜST KUVVETLİ" if prob_ht_o15 >= 35 else ("İ.Y 1.5 ÜST DENENEBİLİR" if prob_ht_o15 >= 25 else "İ.Y 1.5 ÜST ÇOK RİSKLİ")

                st.markdown(f"""
                <div class='alt-market'>
                    <h3 style='color:#00ffcc; margin-top:0; margin-bottom:20px;'>⏱️ Alternatif Marketler (İlk Yarı & Agresyon)</h3>
                    <div style='display:flex; justify-content:space-between; align-items:center;'>
                        <div style='flex:1;'>
                            <span style='color:#8b949e; font-size:15px;'>İlk Yarı Gerçekçi xG:</span><br>
                            <b style='font-size:28px; color:#ffffff;'>{match_expected_ht_goals:.2f}</b><br>
                            <span style='font-size:15px; color:#fff;'>İ.Y 1.5 Üst Şansı: <b style='color:{ht_o15_color};'>%{int(prob_ht_o15)}</b></span><br>
                            <span style='font-size:13px; color:{ht_o15_color}; font-weight:800; background:rgba(255,255,255,0.05); padding:3px 8px; border-radius:5px; margin-top:5px; display:inline-block;'>{ht_text}</span>
                        </div>
                        <div style='width:1px; height:80px; background-color:#1e2530; margin:0 15px;'></div>
                        <div style='flex:1;'>
                            <span style='color:#8b949e; font-size:15px;'>Beklenen Korner:</span><br>
                            <b style='font-size:32px; color:#ffffff;'>{match_expected_corners:.1f}</b><br>
                            <span style='font-size:14px; color:#d4af37; font-weight:bold;'>Toplam Korner Baskısı</span>
                        </div>
                        <div style='width:1px; height:80px; background-color:#1e2530; margin:0 15px;'></div>
                        <div style='flex:1;'>
                            <span style='color:#8b949e; font-size:15px;'>Agresyon (Kart):</span><br>
                            <b style='font-size:32px; color:#ffffff;'>{match_expected_cards:.1f}</b><br>
                            <span style='font-size:13px; color:{"#ff4b4b" if match_expected_cards>4.5 else "#00ffcc"}; font-weight:800; background:rgba(255,255,255,0.05); padding:3px 8px; border-radius:5px; margin-top:5px; display:inline-block;'>{"KIZARABİLİR/SERT MAÇ" if match_expected_cards>4.5 else "DÜŞÜK TANSİYON"}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                xg_html = (
                    f"<div style='background:#121820; padding:30px; border-radius:15px; border-left:6px solid #8a2be2; border: 1px solid #1e2530; box-shadow: 0 4px 15px rgba(0,0,0,0.3);'>"
                    f"<h3 style='color:#8a2be2; margin-top:0; margin-bottom:20px;'>⚽ Gerçek xG Çarpışması (İç Saha vs Dış Saha)</h3>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<div><span style='color:#8b949e; font-size:16px;'>{ev_t} (Ev) xG:</span><br><b style='font-size:32px; color:#ffffff;'>{ev_xg:.2f}</b></div>"
                    f"<div><span style='color:#8b949e; font-size:16px;'>{dep_t} (Dep) xG:</span><br><b style='font-size:32px; color:#ffffff;'>{dep_xg:.2f}</b></div>"
                    f"<div style='text-align:right;'><span style='color:#8b949e; font-size:16px;'>Maçın Toplam xG'si:</span><br><b style='font-size:36px; color:#00ffcc;'>{(ev_xg + dep_xg):.2f}</b></div>"
                    f"</div></div>"
                )
                st.markdown(xg_html, unsafe_allow_html=True)
            
            st.divider()
            st.markdown("<h2 style='color:#d4af37;'>⏳ Zaman Makinesi (Simülasyon Motoru)</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#8b949e; font-size:16px;'>Sistem, veritabanındaki <b>en çok benzeyen 50 geçmiş maça</b> o günün şartlarında 100'er TL yatırsaydınız kasanızın nasıl değişeceğini simüle etti.</p>", unsafe_allow_html=True)
            
            if len(benzer) >= 10:
                sim_df = benzer.head(50).sort_values('Date_Parsed').copy()
                kasa = 0
                kasa_gecmisi = [0]
                
                for _, row in sim_df.iterrows():
                    odds = {'H': row['B365H'], 'D': row['B365D'], 'A': row['B365A']}
                    favori_taraf = min(odds, key=odds.get)
                    favori_oran = odds[favori_taraf]
                    
                    if row['FTR'] == favori_taraf: kasa += (100 * favori_oran) - 100 
                    else: kasa -= 100 
                    kasa_gecmisi.append(kasa)
                
                chart_df = pd.DataFrame({"Maçlar": range(len(kasa_gecmisi)), "Kasa Büyümesi (TL)": kasa_gecmisi}).set_index("Maçlar")
                st.line_chart(chart_df, color="#00ffcc", height=300)
                st.markdown(f"<div style='text-align:center; margin-top:20px;'><span style='font-size:24px;'>50 Maç Sonu Net Kâr/Zarar: </span><b style='font-size:32px; color:{'#00ffcc' if kasa > 0 else '#ff4b4b'};'>{int(kasa)} TL</b></div>", unsafe_allow_html=True)

        else:
            st.error("❌ Veritabanında hiçbir istatistiksel geçerliliği olan benzer maç bulunamadı.")
