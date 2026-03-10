import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests
import io
import re

# --- QUANTUM DESIGN: V188 APEX PREDICTOR (DERİN MATEMATİK & H2H ENTEGRASYONU) ---
st.set_page_config(page_title="V188 | QUANTUM APEX", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    .stApp { background-color: #030507; color: #ffffff; }
    div.stButton > button:first-child { background: linear-gradient(90deg, #d4af37, #ffcc00); color:black; border:none; font-weight:900; height: 3.5em; width: 100%; box-shadow: 0 4px 15px rgba(212, 175, 55, 0.4); text-transform: uppercase; letter-spacing: 1px; }
    .news-card { background-color: #0c1015; padding: 15px; border-radius: 10px; border-left: 5px solid #d4af37; margin-top: 10px; }
    .score-row { background: #121820; padding: 8px; border-radius: 5px; margin-bottom: 5px; display: flex; justify-content: space-between; border: 1px solid #1e2530; font-family: monospace; }
    .danger-zone { background: rgba(255, 75, 75, 0.1); border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .safe-zone { background: rgba(0, 255, 204, 0.1); border-left: 5px solid #00ffcc; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .rank-row { background: #0c1015; padding: 12px; border-radius: 8px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1e2530; transition: transform 0.2s; }
    .rank-row:hover { transform: scale(1.01); border-color: #d4af37; }
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #1a1500); border: 2px solid #d4af37; padding: 25px; border-radius: 15px; text-align: center; box-shadow: 0 0 20px rgba(212, 175, 55, 0.2); margin-top: 20px; }
    .match-count-badge { background: rgba(0, 255, 204, 0.1); border: 1px solid #00ffcc; padding: 15px; border-radius: 10px; margin-bottom: 20px; text-align: center; }
    .api-box { background: #0c1015; border: 1px solid #8a2be2; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
    .scout-box { background: linear-gradient(145deg, #0a0e14, #121820); border: 1px solid #00ffcc; padding: 20px; border-radius: 12px; margin-bottom: 25px; margin-top:20px; box-shadow: 0 4px 15px rgba(0, 255, 204, 0.1); }
    .team-form-container { display: flex; justify-content: space-between; font-size: 15px; align-items: center; }
    .badge-w { background-color: rgba(0, 255, 204, 0.2); color: #00ffcc; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #00ffcc; margin: 0 2px;}
    .badge-d { background-color: rgba(212, 175, 55, 0.2); color: #ffcc00; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #ffcc00; margin: 0 2px;}
    .badge-l { background-color: rgba(255, 75, 75, 0.2); color: #ff4b4b; padding: 2px 6px; border-radius: 4px; font-weight: bold; border: 1px solid #ff4b4b; margin: 0 2px;}
    .prob-card { background: #0c1015; border-radius: 10px; padding: 15px; text-align: center; border: 1px solid #1e2530; margin-bottom: 15px; transition: transform 0.2s; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }
    .prob-card:hover { transform: translateY(-3px); }
    .prob-title { color: #8b949e; font-size: 14px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
    .prob-value { font-size: 32px; font-weight: 900; margin: 5px 0; text-shadow: 0 0 10px rgba(255,255,255,0.1); }
    .prob-odd { color: #ffffff; font-size: 14px; background: #121820; padding: 3px 10px; border-radius: 15px; display: inline-block; border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

default_vals = {'ms1': 2.10, 'msx': 3.30, 'ms2': 3.40, 'o25': 1.90, 'u25': 1.90, 'btts_y': 1.70, 'btts_n': 2.00, 'ev_t': 'Ev Sahibi', 'dep_t': 'Deplasman'}
for k, v in default_vals.items():
    if k not in st.session_state:
        st.session_state[k] = v

LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'E1': 'İngiltere Championship',
    'E2': 'İngiltere League 1', 'E3': 'İngiltere League 2', 'EC': 'İngiltere National League',
    'SP1': 'İspanya La Liga 1', 'SP2': 'İspanya La Liga 2', 'I1': 'İtalya Serie A',
    'I2': 'İtalya Serie B', 'D1': 'Almanya Bundesliga 1', 'D2': 'Almanya Bundesliga 2',
    'F1': 'Fransa Ligue 1', 'F2': 'Fransa Ligue 2', 'N1': 'Hollanda Eredivisie',
    'B1': 'Belçika Pro League', 'P1': 'Portekiz Primeira Liga', 'G1': 'Yunanistan Süper Lig',
    'SC0': 'İskoçya Premiership', 'SC1': 'İskoçya Championship'
}

LEAGUE_WEIGHTS = {
    'E0': 1.5, 'SP1': 1.5, 'I1': 1.5, 'D1': 1.5, 'F1': 1.5,
    'T1': 1.2, 'P1': 1.2, 'N1': 1.2, 'B1': 1.2,
} 

@st.cache_data(ttl=3600)
def load_quantum_data():
    seasons = [
        '2526', '2425', '2324', '2223', '2122', '2021', '1920', '1819', '1718', '1617', 
        '1516', '1415', '1314', '1213', '1112', '1011', '0910', '0809', '0708', '0607', 
        '0506', '0405', '0304', '0203', '0102', '0001'
    ]
    leagues = list(LIG_MAP.keys())
    urls_to_fetch = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in leagues]
    
    def fetch_and_verify(item):
        s, l, url = item
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                return pd.DataFrame()
                
            df = pd.read_csv(io.StringIO(response.text))
            
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG', 'HTHG', 'HTAG', 'HC', 'AC']
            df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H', 'B365D', 'B365A']).copy()
            valid_mask = (df['B365H'] > 1.0) & (df['B365D'] > 1.0) & (df['B365A'] > 1.0)
            margin = (1/df['B365H']) + (1/df['B365D']) + (1/df['B365A'])
            valid_margin = (margin >= 1.01) & (margin <= 1.15)
            df_clean = df[valid_mask & valid_margin].copy()
            df_clean['Season'] = s
            return df_clean
        except:
            return pd.DataFrame()

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

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37;'>👑 Kasa & Finans Yönetimi</h2>", unsafe_allow_html=True)
    kasa_miktari = st.number_input("Güncel Toplam Kasa (TL)", value=10000, step=500)
    st.markdown(f"<div style='background:#0c1015; padding:10px; border-radius:8px; border:1px solid #1e2530;'><b>Aktif Veri Havuzu:</b> {len(db):,} Maç</div>", unsafe_allow_html=True)
    
    if len(db) == 0:
        st.markdown("""
        <div style='background:rgba(255, 75, 75, 0.1); border:1px solid #ff4b4b; padding:10px; border-radius:8px; margin-top:10px;'>
            <span style='color:#ff4b4b; font-size:13px; font-weight:bold;'>⚠️ Veri İndirme Başarısız!</span><br>
            <span style='color:#8b949e; font-size:12px;'>Güvenlik duvarı indirmeyi engelledi. Hayalet Modu'nu devreye sokmak için aşağıdaki butona basın.</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🔄 Hayalet Modu ile Yeniden İndir"):
            st.cache_data.clear()
            st.rerun()
            
    st.divider()
    st.info("🦅 V188 APEX PREDICTOR: Yapay Zeka artık H2H (İkili Rekabet) geçmişini ve İç Saha/Dış Saha (Home/Away) dinamiklerini hesaba katarak kusursuz Net xG hesaplar.")

mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"]
if not db.empty and 'Div' in db.columns:
    mevcut_ligler += sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if k in db['Div'].unique()])
else:
    mevcut_ligler += sorted([f"{k} | {v}" for k, v in LIG_MAP.items()])

st.markdown("<h1 style='text-align:center; color:#d4af37;'>🦅 QUANTUM APEX V188</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#8b949e;'>{datetime.datetime.now().strftime('%d.%m.%Y')} | Derin xG Motoru & İkili Rekabet (H2H) Ağırlığı</p>", unsafe_allow_html=True)

st.markdown("<div class='api-box'>", unsafe_allow_html=True)
st.subheader("⚡ Canlı Oran Borsası (24 Saatlik Hedefler)")

api_c1, api_c2 = st.columns([2, 1])
with api_c1:
    gizli_api = ""
    if "API_KEY" in st.secrets:
        gizli_api = st.secrets["API_KEY"]
    api_key = st.text_input("The-Odds-API Anahtarı (Bulut Kasasına Kilitli):", value=gizli_api, type="password")
    
with api_c2:
    fetch_btn = st.button("🔄 Yaklaşan Maçları Bul (24s)")

if 'live_matches' not in st.session_state:
    st.session_state.live_matches = {}

if fetch_btn and api_key:
    with st.spinner("Önümüzdeki 24 Saat içinde oynanacak maçlar yakından uzağa sıralanıyor..."):
        try:
            clean_key = api_key.strip()
            target_leagues = [
                'soccer_turkey_super_league', 'soccer_epl', 'soccer_spain_la_liga',
                'soccer_italy_serie_a', 'soccer_germany_bundesliga', 'soccer_france_ligue_one',
                'soccer_uefa_champs_league', 'soccer_uefa_europa_league', 'soccer_uefa_europa_conference_league',
                'soccer_netherlands_eredivisie', 'soccer_portugal_primeira_liga', 'soccer_belgium_first_div',
                'soccer_efl_champ', 'soccer_spain_segunda_division', 'soccer_italy_serie_b', 
                'soccer_germany_liga2', 'soccer_france_ligue_two',
                'soccer_japan_j_league', 'soccer_korea_kleague1'
            ]
            
            soccer_count = 0
            current_time_utc = datetime.datetime.now(datetime.timezone.utc)
            horizon_time_utc = current_time_utc + datetime.timedelta(hours=24)
            
            st.session_state.live_matches.clear()
            api_error_message = None
            
            for league in target_leagues:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={clean_key}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
                response = requests.get(url)
                
                if response.status_code == 429:
                    api_error_message = "🚨 KOTA DOLDU: The-Odds-API aylık 500 istek sınırınız tükenmiş! Yeni bir mail ile API almalısınız."
                    break 
                elif response.status_code == 401:
                    api_error_message = "🚨 YETKİSİZ ANAHTAR: API Anahtarınız hatalı, eksik veya silinmiş."
                    break 
                elif response.status_code != 200:
                    continue
                
                matches = response.json()
                for m in matches:
                    try:
                        match_time_utc = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                        local_time = match_time_utc + datetime.timedelta(hours=3)
                        
                        if current_time_utc < match_time_utc < horizon_time_utc:
                            time_str = local_time.strftime('%d.%m %H:%M')
                            baslik = f"[{time_str}] {m['home_team']} - {m['away_team']} | ({m.get('sport_title', 'Lig')})"
                            
                            m['_sort_time'] = match_time_utc.timestamp()
                            st.session_state.live_matches[baslik] = m
                            soccer_count += 1
                    except Exception:
                        pass
            
            if api_error_message:
                st.error(api_error_message)
            elif soccer_count > 0:
                st.success(f"✅ Başarılı! Önümüzdeki 24 saat içinde oynanacak {soccer_count} adet maç bulundu.")
            else:
                st.warning("⚠️ Seçili liglerde önümüzdeki 24 saat içinde maç bulunamadı veya oranlar henüz açılmadı.")
                
        except Exception as e:
            st.error(f"❌ Sistemsel bağlantı hatası: {str(e)}")

if st.session_state.live_matches:
    sel_c1, sel_c2 = st.columns([3, 1])
    with sel_c1:
        sorted_matches = sorted(list(st.session_state.live_matches.keys()), 
                                key=lambda x: st.session_state.live_matches[x]['_sort_time'])
        secilen_mac = st.selectbox("Analiz Edilecek Maçı Seçin:", ["Listeden Seçiniz..."] + sorted_matches)
    with sel_c2:
        if st.button("🚀 Oranları Kutulara Aktar"):
            if secilen_mac != "Listeden Seçiniz...":
                m_data = st.session_state.live_matches[secilen_mac]
                st.session_state.ev_t = m_data['home_team']
                st.session_state.dep_t = m_data['away_team']
                
                ms1_list, msx_list, ms2_list = [], [], []
                o25_list, u25_list = [], []
                
                for bookmaker in m_data.get('bookmakers', []):
                    for market in bookmaker.get('markets', []):
                        if market['key'] == 'h2h':
                            for out in market.get('outcomes', []):
                                if out['name'] == st.session_state.ev_t: ms1_list.append(float(out['price']))
                                elif out['name'] == st.session_state.dep_t: ms2_list.append(float(out['price']))
                                elif out['name'] == 'Draw': msx_list.append(float(out['price']))
                        elif market['key'] == 'totals':
                            for out in market.get('outcomes', []):
                                if out['name'] == 'Over' and out.get('point') == 2.5: o25_list.append(float(out['price']))
                                elif out['name'] == 'Under' and out.get('point') == 2.5: u25_list.append(float(out['price']))
                
                if ms1_list: st.session_state.ms1 = round(sum(ms1_list)/len(ms1_list), 2)
                if msx_list: st.session_state.msx = round(sum(msx_list)/len(msx_list), 2)
                if ms2_list: st.session_state.ms2 = round(sum(ms2_list)/len(ms2_list), 2)
                if o25_list: st.session_state.o25 = round(sum(o25_list)/len(o25_list), 2)
                if u25_list: st.session_state.u25 = round(sum(u25_list)/len(u25_list), 2)
                
                st.rerun() 

st.markdown("</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([1, 1, 1, 1.2])
with c1:
    st.subheader("📊 Taraf Bahisleri")
    ms1 = st.number_input("MS 1", value=st.session_state.ms1, format="%.2f")
    msx = st.number_input("MS X", value=st.session_state.msx, format="%.2f")
    ms2 = st.number_input("MS 2", value=st.session_state.ms2, format="%.2f")
with c2:
    st.subheader("⚽ 2.5 Alt / Üst")
    u25 = st.number_input("2.5 ÜST", value=st.session_state.o25, format="%.2f")
    a25 = st.number_input("2.5 ALT", value=st.session_state.u25, format="%.2f")
with c3:
    st.subheader("🎯 KG Var / Yok")
    kgv = st.number_input("KG VAR", value=st.session_state.btts_y, format="%.2f")
    kgy = st.number_input("KG YOK", value=st.session_state.btts_n, format="%.2f")
with c4:
    st.subheader("🌍 Analiz Rotası")
    ev_t = st.text_input("Ev Sahibi", value=st.session_state.ev_t)
    dep_t = st.text_input("Deplasman", value=st.session_state.dep_t)
    sec_lig = st.selectbox("Havuz Seçimi", mevcut_ligler)
    st.markdown("<p style='font-size:11px; color:#8b949e; margin-top:-10px;'><i>* UEFA, Asya ve Kupa maçları için TÜM DÜNYA seçili bırakın.</i></p>", unsafe_allow_html=True)

def get_clean_team_name(team_name):
    name_map = str.maketrans("éáíóúüöçşğÉÁÍÓÚÜÖÇŞĞ", "eaiouuocsgeaiouuocsg")
    name = str(team_name).translate(name_map).lower().strip()
    
    aliases = {
        "atletico madrid": "Ath Madrid",
        "athletic bilbao": "Ath Bilbao",
        "atletico": "Ath Madrid",
        "athletic": "Ath Bilbao",
        "tottenham": "Tottenham",
        "wolverhampton": "Wolves",
        "wolves": "Wolves",
        "manchester utd": "Man United",
        "manchester united": "Man United",
        "manchester city": "Man City",
        "nott'm forest": "Nott'm Forest",
        "nottingham": "Nott'm Forest",
        "paris sg": "Paris SG",
        "paris saint germain": "Paris SG",
        "psg": "Paris SG",
        "bayern": "Bayern Munich",
        "leverkusen": "Leverkusen",
        "dortmund": "Dortmund",
        "m'gladbach": "M'gladbach",
        "monchengladbach": "M'gladbach",
        "inter": "Inter",
        "ac milan": "Milan",
        "roma": "Roma",
        "napoli": "Napoli",
        "juventus": "Juventus",
        "real madrid": "Real Madrid",
        "barcelona": "Barcelona",
        "galatasaray": "Galatasaray",
        "fenerbahce": "Fenerbahce",
        "besiktas": "Besiktas",
        "sheffield utd": "Sheffield United",
        "sheffield united": "Sheffield United",
        "newcastle": "Newcastle",
        "aston villa": "Aston Villa"
    }
    
    for k, v in aliases.items():
        if k in name:
            return v
            
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

def get_recent_form(team_search_name, df):
    team_matches, actual_search = get_team_df(team_search_name, df)
    if team_matches.empty:
        return 0, 0, 0, 0, 0, 0, 0, []
    
    team_matches['Date_Parsed'] = pd.to_datetime(team_matches['Date'], dayfirst=True, errors='coerce')
    team_matches = team_matches.dropna(subset=['Date_Parsed']).sort_values('Date_Parsed')
    
    last_5 = team_matches.tail(5)
    pts = 0; gs = 0; gc = 0; games_played = len(last_5)
    w = 0; d = 0; l = 0
    seq = []
    
    for _, row in last_5.iterrows():
        is_home = actual_search.lower() in str(row['HomeTeam']).lower()
        if is_home:
            gs += row.get('FTHG', 0)
            gc += row.get('FTAG', 0)
            if row.get('FTR') == 'H': pts += 3; w += 1; seq.append('G')
            elif row.get('FTR') == 'D': pts += 1; d += 1; seq.append('B')
            else: l += 1; seq.append('M')
        else:
            gs += row.get('FTAG', 0)
            gc += row.get('FTHG', 0)
            if row.get('FTR') == 'A': pts += 3; w += 1; seq.append('G')
            elif row.get('FTR') == 'D': pts += 1; d += 1; seq.append('B')
            else: l += 1; seq.append('M')
            
    return pts, gs, gc, games_played, w, d, l, seq

def get_color(prob):
    if prob >= 60: return "#00ffcc" 
    elif prob >= 40: return "#ffcc00" 
    else: return "#ff4b4b" 

def build_seq_html(seq, align="left"):
    if not seq: return ""
    boxes = ""
    for res in seq:
        if res == 'G': boxes += "<span style='background:#00ffcc; color:#000; padding:2px 6px; border-radius:3px; font-weight:bold; margin-right:4px;'>G</span>"
        elif res == 'B': boxes += "<span style='background:#ffcc00; color:#000; padding:2px 6px; border-radius:3px; font-weight:bold; margin-right:4px;'>B</span>"
        elif res == 'M': boxes += "<span style='background:#ff4b4b; color:#fff; padding:2px 6px; border-radius:3px; font-weight:bold; margin-right:4px;'>M</span>"

    justify = "flex-start" if align == "left" else "flex-end"
    return f"<div style='margin-top:10px; display:flex; align-items:center; justify-content:{justify}; font-size:12px;'>{boxes}<span style='color:#8b949e; font-style:italic; margin-left:4px;'>⬅️ Son Maç</span></div>"

if st.button("🚀 TAM OTONOM YAPAY ZEKAYI BAŞLAT"):
    aktif_db = db.copy()
    
    if len(aktif_db) == 0 or 'Div' not in aktif_db.columns:
        st.error("❌ Veritabanı bozuk veya boş! Lütfen sol menüdeki '🔄 Hayalet Modu ile Yeniden İndir' butonuna basın.")
    else:
        for col in ['B365O', 'B365U', 'HTHG', 'HTAG']:
            if col not in aktif_db.columns: aktif_db[col] = np.nan
            
        lig_kodu = None
        if sec_lig != "TÜM DÜNYA (GLOBAL)":
            lig_kodu = sec_lig.split(" | ")[0]
            aktif_db = aktif_db[aktif_db['Div'] == lig_kodu]

        ev_search_name = get_clean_team_name(ev_t)
        dep_search_name = get_clean_team_name(dep_t)

        ev_gecmis, act_ev = get_team_df(ev_search_name, aktif_db)
        dep_gecmis, act_dep = get_team_df(dep_search_name, aktif_db)
        
        with st.spinner("V188 APEX PREDICTOR devrede: İç/Dış Saha dinamikleri ve H2H geçmişi hesaplanıyor..."):
            
            # --- V188 YENİ: İÇ SAHA / DIŞ SAHA GERÇEK xG HESAPLAMASI ---
            # Sadece Ev Sahibinin 'İç Saha' maçları
            ev_home_matches = ev_gecmis[ev_gecmis['HomeTeam'].str.contains(act_ev, case=False, na=False)].tail(5)
            # Sadece Deplasmanın 'Dış Saha' maçları
            dep_away_matches = dep_gecmis[dep_gecmis['AwayTeam'].str.contains(act_dep, case=False, na=False)].tail(5)
            
            ev_scored_home = ev_home_matches['FTHG'].mean() if not ev_home_matches.empty else 1.5
            ev_conceded_home = ev_home_matches['FTAG'].mean() if not ev_home_matches.empty else 1.0
            
            dep_scored_away = dep_away_matches['FTAG'].mean() if not dep_away_matches.empty else 1.1
            dep_conceded_away = dep_away_matches['FTHG'].mean() if not dep_away_matches.empty else 1.5
            
            # Gerçek xG Çarpışması Formülü: (Senin Attığın + Rakibin Yediği) / 2
            true_ev_xg = (ev_scored_home + dep_conceded_away) / 2
            true_dep_xg = (dep_scored_away + ev_conceded_home) / 2

            # --- V188 YENİ: H2H (İKİLİ REKABET) PSİKOLOJİK ÜSTÜNLÜK ---
            h2h_mask = (
                (aktif_db['HomeTeam'].str.contains(act_ev, case=False, na=False) & aktif_db['AwayTeam'].str.contains(act_dep, case=False, na=False)) |
                (aktif_db['HomeTeam'].str.contains(act_dep, case=False, na=False) & aktif_db['AwayTeam'].str.contains(act_ev, case=False, na=False))
            )
            h2h_df = aktif_db[h2h_mask].dropna(subset=['Date']).tail(5)
            
            ev_h2h_pts = 0
            dep_h2h_pts = 0
            if not h2h_df.empty:
                for _, row in h2h_df.iterrows():
                    if act_ev.lower() in str(row['HomeTeam']).lower():
                        if row['FTR'] == 'H': ev_h2h_pts += 3
                        elif row['FTR'] == 'A': dep_h2h_pts += 3
                    else:
                        if row['FTR'] == 'A': ev_h2h_pts += 3
                        elif row['FTR'] == 'H': dep_h2h_pts += 3
                max_pts = len(h2h_df) * 3
                h2h_advantage = (ev_h2h_pts - dep_h2h_pts) / max_pts # -1 ile 1 arası
            else:
                h2h_advantage = 0.0

            # Normal Genel Form
            ev_pts, ev_gs, ev_gc, ev_gp, ev_w, ev_d, ev_l, ev_seq = get_recent_form(ev_search_name, db)
            dep_pts, dep_gs, dep_gc, dep_gp, dep_w, dep_d, dep_l, dep_seq = get_recent_form(dep_search_name, db)
            
            ev_momentum = ((ev_pts / max(ev_gp, 1)) * 5 - 6) * 0.8 if ev_gp > 0 else 0
            dep_momentum = ((dep_pts / max(dep_gp, 1)) * 5 - 6) * 0.8 if dep_gp > 0 else 0

            # Gerçek xG'yi Form İvmesiyle Harmanlıyoruz
            ev_xg = max(0.1, true_ev_xg + (ev_momentum * 0.05))
            dep_xg = max(0.1, true_dep_xg + (dep_momentum * 0.05))

            # Tarihsel Eşleşme Taraması
            hassasiyet = 0.05
            while hassasiyet <= 0.40:
                aktif_db['diff'] = np.sqrt((aktif_db['B365H']-ms1)**2 + (aktif_db['B365A']-ms2)**2 + (aktif_db['B365O'].fillna(u25)-u25)**2)
                benzer = aktif_db[aktif_db['diff'] <= hassasiyet].sort_values('diff')
                if len(benzer) >= 20: break
                hassasiyet += 0.05

        if len(benzer) >= 10:
            benzer = benzer.head(75) 
            
            season_weights = {'2526': 2.0, '2425': 1.8, '2324': 1.6, '2223': 1.4, '2122': 1.2, '2021': 1.0, '1920': 0.8, '1819': 0.7, '1718': 0.6, '1617': 0.5, '1516': 0.4, '1415': 0.3, '1314': 0.2, '1213': 0.1, '1112': 0.1, '1011': 0.1}
            benzer['s_weight'] = benzer['Season'].map(season_weights).fillna(0.1)
            benzer['l_weight'] = benzer['Div'].map(LEAGUE_WEIGHTS).fillna(0.8) if lig_kodu is None else 1.0 
            benzer['weight'] = (1 / (benzer['diff'] + 0.01)) * benzer['s_weight'] * benzer['l_weight']
            w_sum = benzer['weight'].sum()

            raw_p_ms1 = (benzer[benzer['FTR']=='H']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            raw_p_msx = (benzer[benzer['FTR']=='D']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            raw_p_ms2 = (benzer[benzer['FTR']=='A']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
            
            raw_p_u25 = min(99.0, ((benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            raw_p_a25 = 100 - raw_p_u25 if raw_p_u25 > 0 else 0
            raw_p_kgv = min(99.0, ((benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['weight'].sum() / w_sum) * 100)) if 'FTHG' in benzer.columns else 0
            raw_p_kgy = 100 - raw_p_kgv if raw_p_kgv > 0 else 0

            # V188: H2H Psikolojik Ağırlığını ve Form Sapmasını Formüle Ekleme
            ev_sapma = (ev_momentum * 1.5) + (h2h_advantage * 3.0)
            dep_sapma = (dep_momentum * 1.5) - (h2h_advantage * 3.0)
            
            p_ms1 = max(0.1, raw_p_ms1 + ev_sapma - (dep_sapma * 0.5))
            p_ms2 = max(0.1, raw_p_ms2 + dep_sapma - (ev_sapma * 0.5))
            p_msx = max(0.1, 100 - (p_ms1 + p_ms2)) 
            
            toplam_ms = p_ms1 + p_msx + p_ms2
            p_ms1 = (p_ms1 / toplam_ms) * 100
            p_msx = (p_msx / toplam_ms) * 100
            p_ms2 = (p_ms2 / toplam_ms) * 100
            
            # V188: Alt/Üst Oranlarını Gerçek xG Çarpışması İle Etkileme
            xg_sum_diff = (true_ev_xg + true_dep_xg) - 2.5
            p_u25 = min(99.0, max(1.0, raw_p_u25 + (ev_momentum + dep_momentum)*0.5 + (xg_sum_diff * 6.0)))
            p_a25 = 100 - p_u25
            p_kgv = min(99.0, max(1.0, raw_p_kgv + (ev_momentum + dep_momentum)*0.5 + (xg_sum_diff * 4.0)))
            p_kgy = 100 - p_kgv

            ev_color = "#00ffcc" if ev_momentum > 0 else "#ff4b4b"
            dep_color = "#00ffcc" if dep_momentum > 0 else "#ff4b4b"
            
            ev_seq_html = build_seq_html(ev_seq, "left")
            dep_seq_html = build_seq_html(dep_seq, "right")

            form_radar_html = (
                f"<div class='scout-box'>"
                f"<div style='display:flex; align-items:center; margin-bottom:15px; border-bottom:1px solid #1e2530; padding-bottom:10px;'>"
                f"<span style='font-size:20px; margin-right:10px;'>📡</span>"
                f"<h4 style='color:#00ffcc; margin:0;'>PRO Form Radarı (Son {max(ev_gp, dep_gp, 5)} Maç İstatistiği)</h4>"
                f"</div>"
                f"<div class='team-form-container'>"
                f"<div style='flex:1; padding-right:10px;'>"
                f"<div style='font-size:18px; font-weight:bold; color:#ffffff; margin-bottom:5px;'>🔵 {ev_t} (Ev)</div>"
                f"<div style='margin-bottom:8px;'>"
                f"<span class='badge-w'>{ev_w}G</span>"
                f"<span class='badge-d'>{ev_d}B</span>"
                f"<span class='badge-l'>{ev_l}M</span>"
                f"</div>"
                f"<div style='color:#8b949e; font-size:13px; line-height:1.6;'>"
                f"<b>Toplanan Puan:</b> <span style='color:#fff'>{ev_pts}</span><br>"
                f"<b>Gol (A/Y):</b> <span style='color:#00ffcc'>{ev_gs}</span> - <span style='color:#ff4b4b'>{ev_gc}</span><br>"
                f"<b>Momentum İvmesi:</b> <span style='color: {ev_color}; font-weight:bold;'>{ev_momentum:.1f}</span>"
                f"</div>"
                f"{ev_seq_html}"
                f"</div>"
                f"<div style='width:1px; background-color:#1e2530; margin:0 15px;'></div>"
                f"<div style='flex:1; padding-left:10px; text-align:right;'>"
                f"<div style='font-size:18px; font-weight:bold; color:#ffffff; margin-bottom:5px;'>🔴 {dep_t} (Dep)</div>"
                f"<div style='margin-bottom:8px;'>"
                f"<span class='badge-w'>{dep_w}G</span>"
                f"<span class='badge-d'>{dep_d}B</span>"
                f"<span class='badge-l'>{dep_l}M</span>"
                f"</div>"
                f"<div style='color:#8b949e; font-size:13px; line-height:1.6;'>"
                f"<span style='color:#fff'>{dep_pts}</span> <b>:Toplanan Puan</b><br>"
                f"<span style='color:#00ffcc'>{dep_gs}</span> - <span style='color:#ff4b4b'>{dep_gc}</span> <b>:(A/Y) Gol</b><br>"
                f"<span style='color: {dep_color}; font-weight:bold;'>{dep_momentum:.1f}</span> <b>:Momentum İvmesi</b>"
                f"</div>"
                f"{dep_seq_html}"
                f"</div>"
                f"</div>"
                f"</div>"
            )
            st.markdown(form_radar_html, unsafe_allow_html=True)
            
            st.markdown("<h3 style='margin-bottom:15px; color:#ffffff;'>📊 Taraf & Skor İhtimalleri</h3>", unsafe_allow_html=True)
            r1_c1, r1_c2, r1_c3 = st.columns(3)
            
            p_ms1_c = get_color(p_ms1)
            r1_c1.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_ms1_c};'>"
                f"<div class='prob-title'>{ev_t} Kazanır</div>"
                f"<div class='prob-value' style='color:{p_ms1_c};'>%{int(p_ms1)}</div>"
                f"<div class='prob-odd'>Oran: {ms1}</div>"
                f"</div>", unsafe_allow_html=True)
            
            p_msx_c = get_color(p_msx)
            r1_c2.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_msx_c};'>"
                f"<div class='prob-title'>Beraberlik</div>"
                f"<div class='prob-value' style='color:{p_msx_c};'>%{int(p_msx)}</div>"
                f"<div class='prob-odd'>Oran: {msx}</div>"
                f"</div>", unsafe_allow_html=True)
            
            p_ms2_c = get_color(p_ms2)
            r1_c3.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_ms2_c};'>"
                f"<div class='prob-title'>{dep_t} Kazanır</div>"
                f"<div class='prob-value' style='color:{p_ms2_c};'>%{int(p_ms2)}</div>"
                f"<div class='prob-odd'>Oran: {ms2}</div>"
                f"</div>", unsafe_allow_html=True)

            r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
            
            p_u25_c = get_color(p_u25)
            r2_c1.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_u25_c};'>"
                f"<div class='prob-title'>2.5 ÜST</div>"
                f"<div class='prob-value' style='color:{p_u25_c};'>%{int(p_u25)}</div>"
                f"<div class='prob-odd'>Oran: {u25}</div>"
                f"</div>", unsafe_allow_html=True)

            p_a25_c = get_color(p_a25)
            r2_c2.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_a25_c};'>"
                f"<div class='prob-title'>2.5 ALT</div>"
                f"<div class='prob-value' style='color:{p_a25_c};'>%{int(p_a25)}</div>"
                f"<div class='prob-odd'>Oran: {a25}</div>"
                f"</div>", unsafe_allow_html=True)

            p_kgv_c = get_color(p_kgv)
            r2_c3.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_kgv_c};'>"
                f"<div class='prob-title'>KG VAR</div>"
                f"<div class='prob-value' style='color:{p_kgv_c};'>%{int(p_kgv)}</div>"
                f"<div class='prob-odd'>Oran: {kgv}</div>"
                f"</div>", unsafe_allow_html=True)

            p_kgy_c = get_color(p_kgy)
            r2_c4.markdown(
                f"<div class='prob-card' style='border-top: 4px solid {p_kgy_c};'>"
                f"<div class='prob-title'>KG YOK</div>"
                f"<div class='prob-value' style='color:{p_kgy_c};'>%{int(p_kgy)}</div>"
                f"<div class='prob-odd'>Oran: {kgy}</div>"
                f"</div>", unsafe_allow_html=True)

            st.divider()

            targets = [
                ("MS 1", p_ms1, ms1), ("MS X", p_msx, msx), ("MS 2", p_ms2, ms2), 
                ("2.5 Üst", p_u25, u25), ("2.5 Alt", p_a25, a25),
                ("KG Var", p_kgv, kgv), ("KG Yok", p_kgy, kgy)
            ]

            det_l, det_r = st.columns(2)
            with det_l:
                st.subheader("🧠 Tam Otonom Banko Tahmini")
                
                en_guvenilir_tahmin = None
                en_yuksek_ihtimal = -1
                
                for t in targets:
                    name, prob, odd = t
                    if prob > en_yuksek_ihtimal:
                        en_yuksek_ihtimal = prob
                        en_guvenilir_tahmin = t

                name, prob, odd = en_guvenilir_tahmin
                
                b_val = odd - 1
                p_val = prob / 100
                q_val = 1 - p_val
                kelly_fraction = ((b_val * p_val) - q_val) / b_val if b_val > 0 else 0
                quarter_kelly = max(0, (kelly_fraction / 4))
                
                if quarter_kelly > 0:
                    onerilen_yatirim = min(kasa_miktari * quarter_kelly, kasa_miktari * 0.05)
                    yatirim_notu = f"<b style='color:#00ffcc; font-size:16px;'>💰 Güvenli Kasa Oranı (Kelly): {int(onerilen_yatirim)} TL</b>"
                else:
                    yatirim_notu = f"<span style='color:#ffcc00; font-size:14px;'>⚠️ Oran düşük olduğu için uzun vadeli yatırım değil, günlük banko/kombine bahsidir.</span>"
                
                ai_mesaj = f"Takımların Genel formunu, İÇ/DIŞ saha özel performanslarını ve Aralarındaki Psikolojik Rekabeti (H2H) 25 yıllık veriyle harmanladım. Olasılığı en yüksek senaryo budur:"

                ai_verdict_html = (
                    f"<div class='ai-verdict-box'>"
                    f"<p style='color:#8b949e; font-size:14px; text-align:left; font-style:italic;'>\"{ai_mesaj}\"</p>"
                    f"<h1 style='color:#d4af37; font-size: 40px; margin: 10px 0;'>🎯 {name} 🎯</h1>"
                    f"<div style='display: flex; justify-content: space-around; margin: 20px 0;'>"
                    f"<div><span style='color:#8b949e;'>Dinamik İhtimal:</span><br><b style='font-size:24px; color:#00ffcc;'>%{int(prob)}</b></div>"
                    f"<div><span style='color:#8b949e;'>Piyasa Oranı:</span><br><b style='font-size:24px;'>{odd:.2f}</b></div>"
                    f"</div>"
                    f"<hr style='border-color: #333;'>"
                    f"{yatirim_notu}"
                    f"</div>"
                )
                st.markdown(ai_verdict_html, unsafe_allow_html=True)

                st.divider()
                
                st.subheader("🏆 İhtimal Hiyerarşisi")
                sirali_ihtimaller = sorted(targets, key=lambda x: x[1], reverse=True)
                for i, (isim, i_prob, i_odd) in enumerate(sirali_ihtimaller):
                    renk = "#00ffcc" if i_prob >= 60 else ("#d4af37" if i_prob >= 40 else "#ff4b4b")
                    st.markdown(
                        f"<div class='rank-row' style='border-left: 5px solid {renk}; margin-bottom: 5px;'>"
                        f"<span style='font-size: 15px;'><b>{i+1}.</b> {isim}</span>"
                        f"<span style='color:{renk}; font-weight:900; font-size:18px;'>%{int(i_prob)}</span>"
                        f"</div>", 
                        unsafe_allow_html=True
                    )

            with det_r:
                st.subheader("📈 Dinamik Skor Matrisi (Poisson)")
                
                score_probs = {}
                for h in range(5):
                    for a in range(5):
                        prob = poisson.pmf(h, ev_xg) * poisson.pmf(a, dep_xg) * 100
                        score_probs[f"{h} - {a}"] = prob
                        
                sorted_scores = sorted(score_probs.items(), key=lambda x: x[1], reverse=True)[:6]
                
                st.markdown("<p style='color:#8b949e; font-size:13px; margin-bottom:5px;'>Yapay Zeka Formüllerine Göre En Olası Skorlar:</p>", unsafe_allow_html=True)
                
                # Streamlit'in Alfabetik Sıralamasını Kırmak İçin Özel Hile (Rakamlar Eklendi)
                chart_data = pd.DataFrame({
                    "Skorlar": [f"{i+1}. İhtimal ({s[0]})" for i, s in enumerate(sorted_scores)],
                    "İhtimal (%)": [int(s[1]) for s in sorted_scores]
                }).set_index("Skorlar")
                st.bar_chart(chart_data, color="#d4af37", height=200)
                
                st.divider()

                xg_html = (
                    f"<div style='background:#121820; padding:20px; border-radius:10px; border-left:5px solid #8a2be2; border: 1px solid #1e2530;'>"
                    f"<h4 style='color:#8a2be2; margin-top:0; margin-bottom:15px;'>⚽ Gerçek xG Çarpışması (İç Saha vs Dış Saha)</h4>"
                    f"<div style='display:flex; justify-content:space-between; align-items:center;'>"
                    f"<div>"
                    f"<span style='color:#8b949e; font-size:14px;'>{ev_t} (Ev) xG:</span><br>"
                    f"<b style='font-size:24px; color:#ffffff;'>{ev_xg:.2f}</b>"
                    f"</div>"
                    f"<div>"
                    f"<span style='color:#8b949e; font-size:14px;'>{dep_t} (Dep) xG:</span><br>"
                    f"<b style='font-size:24px; color:#ffffff;'>{dep_xg:.2f}</b>"
                    f"</div>"
                    f"<div style='text-align:right;'>"
                    f"<span style='color:#8b949e; font-size:14px;'>Maçın Toplam xG'si:</span><br>"
                    f"<b style='font-size:26px; color:#00ffcc;'>{(ev_xg + dep_xg):.2f}</b>"
                    f"</div>"
                    f"</div>"
                    f"</div>"
                )
                st.markdown(xg_html, unsafe_allow_html=True)

        else:
            st.error("❌ Veritabanında hiçbir istatistiksel geçerliliği olan benzer maç bulunamadı.")
