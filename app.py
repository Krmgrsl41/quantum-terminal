import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests

# --- QUANTUM DESIGN: V174 FLAWLESS UI (HATA GİDERME & SOLA DAYALI HTML) ---
st.set_page_config(page_title="V174 | QUANTUM PRO", layout="wide", page_icon="💎")

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
        try:
            df = pd.read_csv(url)
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(fetch_and_verify, urls_to_fetch))
        
    for res_df in results:
        if not res_df.empty:
            dfs.append(res_df)
            
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

db = load_quantum_data()

with st.sidebar:
    st.markdown("<h2 style='color:#d4af37;'>👑 Kasa & Finans Yönetimi</h2>", unsafe_allow_html=True)
    kasa_miktari = st.number_input("Güncel Toplam Kasa (TL)", value=10000, step=500)
    st.markdown(f"<div style='background:#0c1015; padding:10px; border-radius:8px; border:1px solid #1e2530;'><b>Aktif Veri Havuzu:</b> {len(db):,} Maç</div>", unsafe_allow_html=True)
    st.divider()
    st.info("💎 V174 FLAWLESS UI: Form Radarı görsel hatası giderildi. Dinamik kartlar aktif.")

mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"] + sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if k in db['Div'].unique()])

st.markdown("<h1 style='text-align:center; color:#d4af37;'>💎 QUANTUM PRO V174</h1>", unsafe_allow_html=True)
st.markdown(f"<p style='text-align:center; color:#8b949e;'>{datetime.datetime.now().strftime('%d.%m.%Y')} | Gelişmiş Dinamik Arayüz & Odaklı Radar</p>", unsafe_allow_html=True)

st.markdown("<div class='api-box'>", unsafe_allow_html=True)
st.subheader("⚡ Canlı Oran Borsası (Günün Hedefleri)")

api_c1, api_c2 = st.columns([2, 1])
with api_c1:
    gizli_api = ""
    if "API_KEY" in st.secrets:
        gizli_api = st.secrets["API_KEY"]
    api_key = st.text_input("The-Odds-API Anahtarı (Bulut Kasasına Kilitli):", value=gizli_api, type="password")
    
with api_c2:
    fetch_btn = st.button("🔄 Bugünün Fırsatlarını Bul")

if 'live_matches' not in st.session_state:
    st.session_state.live_matches = {}

if fetch_btn and api_key:
    with st.spinner("Bugün oynanacak maçlar aranıyor ve saati yaklaşanlar öne alınıyor..."):
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
            current_time_tr = current_time_utc + datetime.timedelta(hours=3)
            today_date = current_time_tr.date()
            
            st.session_state.live_matches.clear()
            
            for league in target_leagues:
                url = f"https://api.the-odds-api.com/v4/sports/{league}/odds/?apiKey={clean_key}&regions=eu,uk&markets=h2h,totals&oddsFormat=decimal"
                response = requests.get(url)
                
                if response.status_code == 200:
                    matches = response.json()
                    for m in matches:
                        try:
                            match_time_utc = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                            local_time = match_time_utc + datetime.timedelta(hours=3)
                            
                            if match_time_utc > current_time_utc and local_time.date() == today_date:
                                time_str = local_time.strftime('%H:%M')
                                baslik = f"[{time_str}] {m['home_team']} - {m['away_team']} | ({m.get('sport_title', 'Lig')})"
                                
                                m['_sort_time'] = match_time_utc.timestamp()
                                st.session_state.live_matches[baslik] = m
                                soccer_count += 1
                        except Exception:
                            pass
            
            if soccer_count > 0:
                st.success(f"✅ Başarılı! Sadece BUGÜN oynanacak tam {soccer_count} hedef maç bulundu.")
            else:
                st.warning("⚠️ Bağlantı başarılı ancak hedef 19 ligde BUGÜN için başlamamış maç bulunmuyor.")
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
    st.markdown("<p style='font-size:11px; color:#8b949e; margin-top:-10px;'><i>* UEFA, Japonya ve Kore maçları için TÜM DÜNYA seçili bırakın.</i></p>", unsafe_allow_html=True)

def get_recent_form(team_name, df):
    team_matches = df[(df['HomeTeam'].str.contains(team_name, case=False, na=False)) | 
                      (df['AwayTeam'].str.contains(team_name, case=False, na=False))].copy()
    if team_matches.empty:
        return 0, 0, 0, 0, 0, 0, 0
    
    last_5 = team_matches.tail(5)
    pts = 0; gs = 0; gc = 0; games_played = len(last_5)
    w = 0; d = 0; l = 0
    
    for _, row in last_5.iterrows():
        is_home = team_name.lower() in str(row['HomeTeam']).lower()
        if is_home:
            gs += row.get('FTHG', 0)
            gc += row.get('FTAG', 0)
            if row.get('FTR') == 'H': pts += 3; w += 1
            elif row.get('FTR') == 'D': pts += 1; d += 1
            else: l += 1
        else:
            gs += row.get('FTAG', 0)
            gc += row.get('FTHG', 0)
            if row.get('FTR') == 'A': pts += 3; w += 1
            elif row.get('FTR') == 'D': pts += 1; d += 1
            else: l += 1
            
    return pts, gs, gc, games_played, w, d, l

def get_color(prob):
    if prob >= 60: return "#00ffcc" 
    elif prob >= 40: return "#ffcc00" 
    else: return "#ff4b4b" 

if st.button("🚀 TAM OTONOM YAPAY ZEKAYI BAŞLAT"):
    aktif_db = db.copy()
    
    for col in ['B365O', 'B365U', 'HTHG', 'HTAG']:
        if col not in aktif_db.columns: aktif_db[col] = np.nan
        
    lig_kodu = None
    if sec_lig != "TÜM DÜNYA (GLOBAL)":
        lig_kodu = sec_lig.split(" | ")[0]
        aktif_db = aktif_db[aktif_db['Div'] == lig_kodu]

    ev_gecmis = aktif_db[aktif_db['HomeTeam'].str.contains(ev_t, case=False, na=False, regex=False)] if 'HomeTeam' in aktif_db.columns else pd.DataFrame()
    dep_gecmis = aktif_db[aktif_db['AwayTeam'].str.contains(dep_t, case=False, na=False, regex=False)] if 'AwayTeam' in aktif_db.columns else pd.DataFrame()
    
    ham_ev_xg = ev_gecmis['FTHG'].mean() if not ev_gecmis.empty and 'FTHG' in ev_gecmis.columns else 1.5
    ham_dep_xg = dep_gecmis['FTAG'].mean() if not dep_gecmis.empty and 'FTAG' in dep_gecmis.columns else 1.1

    global_u25_avg = (db['FTHG'] + db['FTAG'] > 2.5).mean() if 'FTHG' in db.columns else 0.5
    league_u25_mod = 1.0
    if lig_kodu and 'FTHG' in aktif_db.columns:
        lig_u25_avg = (aktif_db['FTHG'] + aktif_db['FTAG'] > 2.5).mean()
        league_u25_mod = lig_u25_avg / global_u25_avg if global_u25_avg > 0 else 1.0

    with st.spinner("Otomatik Form Radarı devrede, takımların son 5 maçı taranıyor..."):
        
        ev_pts, ev_gs, ev_gc, ev_gp, ev_w, ev_d, ev_l = get_recent_form(ev_t, db)
        dep_pts, dep_gs, dep_gc, dep_gp, dep_w, dep_d, dep_l = get_recent_form(dep_t, db)
        
        ev_momentum = ((ev_pts / max(ev_gp, 1)) * 5 - 6) * 0.8 if ev_gp > 0 else 0
        dep_momentum = ((dep_pts / max(dep_gp, 1)) * 5 - 6) * 0.8 if dep_gp > 0 else 0

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
        
        if lig_kodu is None:
            benzer['l_weight'] = benzer['Div'].map(LEAGUE_WEIGHTS).fillna(0.8)
        else:
            benzer['l_weight'] = 1.0 
            
        benzer['weight'] = (1 / (benzer['diff'] + 0.01)) * benzer['s_weight'] * benzer['l_weight']
        w_sum = benzer['weight'].sum()

        raw_p_ms1 = (benzer[benzer['FTR']=='H']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
        raw_p_msx = (benzer[benzer['FTR']=='D']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
        raw_p_ms2 = (benzer[benzer['FTR']=='A']['weight'].sum() / w_sum) * 100 if 'FTR' in benzer.columns else 0
        
        raw_p_u25 = min(99.0, ((benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['weight'].sum() / w_sum) * 100) * league_u25_mod) if 'FTHG' in benzer.columns else 0
        raw_p_a25 = 100 - raw_p_u25 if raw_p_u25 > 0 else 0
        raw_p_kgv = min(99.0, ((benzer[(benzer['FTHG']>0) & (benzer['FTAG']>0)]['weight'].sum() / w_sum) * 100) * league_u25_mod) if 'FTHG' in benzer.columns else 0
        raw_p_kgy = 100 - raw_p_kgv if raw_p_kgv > 0 else 0

        ev_sapma = ev_momentum * 1.5
        dep_sapma = dep_momentum * 1.5
        
        p_ms1 = max(0.1, raw_p_ms1 + ev_sapma - (dep_sapma * 0.5))
        p_ms2 = max(0.1, raw_p_ms2 + dep_sapma - (ev_sapma * 0.5))
        p_msx = max(0.1, 100 - (p_ms1 + p_ms2)) 
        
        toplam_ms = p_ms1 + p_msx + p_ms2
        p_ms1 = (p_ms1 / toplam_ms) * 100
        p_msx = (p_msx / toplam_ms) * 100
        p_ms2 = (p_ms2 / toplam_ms) * 100
        
        ev_xg = max(0.1, ham_ev_xg + (ev_momentum * 0.05))
        dep_xg = max(0.1, ham_dep_xg + (dep_momentum * 0.05))

        total_form = ev_momentum + dep_momentum
        p_u25 = min(99.0, max(1.0, raw_p_u25 + (total_form * 1.0)))
        p_a25 = 100 - p_u25
        p_kgv = min(99.0, max(1.0, raw_p_kgv + (total_form * 1.0)))
        p_kgy = 100 - p_kgv

        st.markdown(f"""
<div class='scout-box'>
    <div style='display:flex; align-items:center; margin-bottom:15px; border-bottom:1px solid #1e2530; padding-bottom:10px;'>
        <span style='font-size:20px; margin-right:10px;'>📡</span>
        <h4 style='color:#00ffcc; margin:0;'>PRO Form Radarı (Son {max(ev_gp, dep_gp, 5)} Maç İstatistiği)</h4>
    </div>
    
    <div class='team-form-container'>
        <div style='flex:1; padding-right:10px;'>
            <div style='font-size:18px; font-weight:bold; color:#ffffff; margin-bottom:5px;'>🔵 {ev_t} (Ev)</div>
            <div style='margin-bottom:8px;'>
                <span class='badge-w'>{ev_w}G</span>
                <span class='badge-d'>{ev_d}B</span>
                <span class='badge-l'>{ev_l}M</span>
            </div>
            <div style='color:#8b949e; font-size:13px; line-height:1.6;'>
                <b>Toplanan Puan:</b> <span style='color:#fff'>{ev_pts}</span><br>
                <b>Gol (A/Y):</b> <span style='color:#00ffcc'>{ev_gs}</span> - <span style='color:#ff4b4b'>{ev_gc}</span><br>
                <b>Momentum İvmesi:</b> <span style='color: {"#00ffcc" if ev_momentum>0 else "#ff4b4b"}; font-weight:bold;'>{ev_momentum:.1f}</span>
            </div>
        </div>
        
        <div style='width:1px; background-color:#1e2530; margin:0 15px;'></div>
        
        <div style='flex:1; padding-left:10px; text-align:right;'>
            <div style='font-size:18px; font-weight:bold; color:#ffffff; margin-bottom:5px;'>🔴 {dep_t} (Dep)</div>
            <div style='margin-bottom:8px;'>
                <span class='badge-w'>{dep_w}G</span>
                <span class='badge-d'>{dep_d}B</span>
                <span class='badge-l'>{dep_l}M</span>
            </div>
            <div style='color:#8b949e; font-size:13px; line-height:1.6;'>
                <span style='color:#fff'>{dep_pts}</span> <b>:Toplanan Puan</b><br>
                <span style='color:#00ffcc'>{dep_gs}</span> - <span style='color:#ff4b4b'>{dep_gc}</span> <b>:(A/Y) Gol</b><br>
                <span style='color: {"#00ffcc" if dep_momentum>0 else "#ff4b4b"}; font-weight:bold;'>{dep_momentum:.1f}</span> <b>:Momentum İvmesi</b>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
        
        st.markdown("<h3 style='margin-bottom:15px; color:#ffffff;'>📊 Taraf & Skor İhtimalleri</h3>", unsafe_allow_html=True)
        r1_c1, r1_c2, r1_c3 = st.columns(3)
        
        r1_c1.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_ms1)};'>
    <div class='prob-title'>{ev_t} Kazanır</div>
    <div class='prob-value' style='color:{get_color(p_ms1)};'>%{int(p_ms1)}</div>
    <div class='prob-odd'>Oran: {ms1}</div>
</div>""", unsafe_allow_html=True)
        
        r1_c2.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_msx)};'>
    <div class='prob-title'>Beraberlik</div>
    <div class='prob-value' style='color:{get_color(p_msx)};'>%{int(p_msx)}</div>
    <div class='prob-odd'>Oran: {msx}</div>
</div>""", unsafe_allow_html=True)
        
        r1_c3.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_ms2)};'>
    <div class='prob-title'>{dep_t} Kazanır</div>
    <div class='prob-value' style='color:{get_color(p_ms2)};'>%{int(p_ms2)}</div>
    <div class='prob-odd'>Oran: {ms2}</div>
</div>""", unsafe_allow_html=True)

        r2_c1, r2_c2, r2_c3, r2_c4 = st.columns(4)
        
        r2_c1.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_u25)};'>
    <div class='prob-title'>2.5 ÜST</div>
    <div class='prob-value' style='color:{get_color(p_u25)};'>%{int(p_u25)}</div>
    <div class='prob-odd'>Oran: {u25}</div>
</div>""", unsafe_allow_html=True)

        r2_c2.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_a25)};'>
    <div class='prob-title'>2.5 ALT</div>
    <div class='prob-value' style='color:{get_color(p_a25)};'>%{int(p_a25)}</div>
    <div class='prob-odd'>Oran: {a25}</div>
</div>""", unsafe_allow_html=True)

        r2_c3.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_kgv)};'>
    <div class='prob-title'>KG VAR</div>
    <div class='prob-value' style='color:{get_color(p_kgv)};'>%{int(p_kgv)}</div>
    <div class='prob-odd'>Oran: {kgv}</div>
</div>""", unsafe_allow_html=True)

        r2_c4.markdown(f"""
<div class='prob-card' style='border-top: 4px solid {get_color(p_kgy)};'>
    <div class='prob-title'>KG YOK</div>
    <div class='prob-value' style='color:{get_color(p_kgy)};'>%{int(p_kgy)}</div>
    <div class='prob-odd'>Oran: {kgy}</div>
</div>""", unsafe_allow_html=True)

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
            
            ai_mesaj = f"Takımların güncel form momentumunu otomatik olarak ölçtüm ve 25 yıllık veriyle harmanladım. Bu maçta ihtimali en yüksek senaryo şudur:"

            st.markdown(f"""
<div class='ai-verdict-box'>
    <p style='color:#8b949e; font-size:14px; text-align:left; font-style:italic;'>"{ai_mesaj}"</p>
    <h1 style='color:#d4af37; font-size: 40px; margin: 10px 0;'>🎯 {name} 🎯</h1>
    <div style='display: flex; justify-content: space-around; margin: 20px 0;'>
        <div><span style='color:#8b949e;'>Dinamik İhtimal:</span><br><b style='font-size:24px; color:#00ffcc;'>%{int(prob)}</b></div>
        <div><span style='color:#8b949e;'>Piyasa Oranı:</span><br><b style='font-size:24px;'>{odd:.2f}</b></div>
    </div>
    <hr style='border-color: #333;'>
    {yatirim_notu}
</div>
""", unsafe_allow_html=True)

            st.divider()
            
            st.subheader("🏆 İhtimal Hiyerarşisi")
            sirali_ihtimaller = sorted(targets, key=lambda x: x[1], reverse=True)
            for i, (isim, i_prob, i_odd) in enumerate(sirali_ihtimaller):
                renk = "#00ffcc" if i_prob >= 60 else ("#d4af37" if i_prob >= 40 else "#ff4b4b")
                st.markdown(f"""<div class='rank-row' style='border-left: 5px solid {renk}; margin-bottom: 5px;'>
                    <span style='font-size: 15px;'><b>{i+1}.</b> {isim}</span>
                    <span style='color:{renk}; font-weight:900; font-size:18px;'>%{int(i_prob)}</span>
                </div>""", unsafe_allow_html=True)

        with det_r:
            st.subheader("📈 Tarihsel Skor Matrisi")
            harman_hg = np.nan_to_num((benzer['FTHG'].mean() + ev_xg) / 2, nan=1.0)
            harman_ag = np.nan_to_num((benzer['FTAG'].mean() + dep_xg) / 2, nan=1.0)
            
            benzer_skor = benzer.dropna(subset=['FTHG', 'FTAG']).copy()
            benzer_skor['Skor'] = benzer_skor['FTHG'].astype(int).astype(str) + "-" + benzer_skor['FTAG'].astype(int).astype(str)
            skor_counts = benzer_skor['Skor'].value_counts()
            
            st.markdown("<p style='color:#8b949e; font-size:13px; margin-bottom:5px;'>En Olası Skor Dağılımı Grafiği:</p>", unsafe_allow_html=True)
            chart_data = pd.DataFrame({
                "Skorlar": list(skor_counts.head(6).keys()),
                "İhtimal (%)": [int((c / len(benzer_skor)) * 100) for c in skor_counts.head(6).values]
            }).set_index("Skorlar")
            st.bar_chart(chart_data, color="#d4af37", height=200)
            
            st.divider()

            st.markdown(f"""
<div style='background:#121820; padding:20px; border-radius:10px; border-left:5px solid #8a2be2; border: 1px solid #1e2530;'>
    <h4 style='color:#8a2be2; margin-top:0; margin-bottom:15px;'>⚽ Güncel xG Beklentisi (Form Destekli)</h4>
    <div style='display:flex; justify-content:space-between; align-items:center;'>
        <div>
            <span style='color:#8b949e; font-size:14px;'>{ev_t} (Ev) xG:</span><br>
            <b style='font-size:24px; color:#ffffff;'>{ev_xg:.2f}</b>
        </div>
        <div>
            <span style='color:#8b949e; font-size:14px;'>{dep_t} (Dep) xG:</span><br>
            <b style='font-size:24px; color:#ffffff;'>{dep_xg:.2f}</b>
        </div>
        <div style='text-align:right;'>
            <span style='color:#8b949e; font-size:14px;'>Maçın Toplam xG'si:</span><br>
            <b style='font-size:26px; color:#00ffcc;'>{(ev_xg + dep_xg):.2f}</b>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    else:
        st.error("❌ Veritabanında hiçbir istatistiksel geçerliliği olan benzer maç bulunamadı.")
