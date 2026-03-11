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

# --- QUANTUM DESIGN: V197 THE INSTINCT (SURVIVAL MODE & EXTREME MARKETS) ---
st.set_page_config(page_title="V197 | QUANTUM INSTINCT", layout="wide", page_icon="🧿")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    div.stButton > button:first-child { 
        background: linear-gradient(90deg, #d4af37, #ffcc00); color:black; border:none; 
        font-weight:900; font-size: 18px; height: 3.5em; width: 100%; 
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); text-transform: uppercase; letter-spacing: 1.5px; border-radius: 12px;
    }
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #151100); border: 2px solid #d4af37; padding: 35px; border-radius: 20px; text-align: center; margin-top: 20px; }
    .api-box { background: #0c1015; border: 1px solid #8a2be2; padding: 25px; border-radius: 15px; margin-bottom: 25px; }
    .scout-box { background: linear-gradient(145deg, #0a0e14, #121820); border: 1px solid #00ffcc; padding: 30px; border-radius: 15px; margin-bottom: 25px; }
    .prob-card { background: #0c1015; border-radius: 15px; padding: 20px 10px; text-align: center; border: 1px solid #1e2530; margin-bottom: 15px; }
    .prob-value { font-size: 38px; font-weight: 900; margin: 5px 0; }
    .rank-row { background: #0c1015; padding: 18px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; border: 1px solid #1e2530; }
    .syndicate-badge { background: #1a1500; border: 1px solid #d4af37; color: #d4af37; padding: 5px 10px; border-radius: 6px; font-size: 13px; font-weight: 800; margin-right: 6px; }
    .survival-mode { background: linear-gradient(90deg, #ff4b4b, #800000); padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 15px; border: 2px solid #fff; animation: pulse 2s infinite; }
    @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; } 100% { opacity: 0.8; } }
    </style>
    """, unsafe_allow_html=True)

# Session State Hazırlığı
defaults = {'ms1':2.10, 'msx':3.30, 'ms2':3.40, 'o15':1.25, 'o25':1.90, 'o35':3.20, 'u25':1.90, 'btts_y':1.70, 'btts_n':2.00, 'ev_t':'Ev Sahibi', 'dep_t':'Deplasman'}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'E1': 'İngiltere Championship',
    'SP1': 'İspanya La Liga 1', 'I1': 'İtalya Serie A', 'D1': 'Almanya Bundesliga 1', 'F1': 'Fransa Ligue 1'
}

LEAGUE_DNA = {
    'T1': {'name': 'Kaos ve Agresyon (Süper Lig)', 'card_mod': 1.3, 'xg_mod': 1.05, 'corner_mod': 1.0},
    'D1': {'name': 'Açık Alan / Yüksek Tempo (Bundesliga)', 'card_mod': 0.8, 'xg_mod': 1.20, 'corner_mod': 1.1},
    'E0': {'name': 'Yüksek Yoğunluk (Premier Lig)', 'card_mod': 0.85, 'xg_mod': 1.10, 'corner_mod': 1.25}
}

@st.cache_data(ttl=3600)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223', '2122', '2021']
    leagues = list(LIG_MAP.keys())
    dfs = []
    for s in seasons:
        for l in leagues:
            try:
                url = f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv'
                df = pd.read_csv(url)
                if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
                cols = ['Div','Date','HomeTeam','AwayTeam','B365H','B365D','B365A','B365O','B365U','FTR','FTHG','FTAG','HTHG','HTAG','HC','AC','HST','AST','HY','AY','HR','AR']
                df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H','FTR'])
                df['Season'] = s
                dfs.append(df)
            except: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

db = load_quantum_data()

with st.sidebar:
    st.markdown("<h3 style='color:#00ffcc;'>🎛️ Radar Kalibrasyonu</h3>", unsafe_allow_html=True)
    value_threshold = st.slider("🚨 Value Alarm Hassasiyeti (%)", 3, 25, 10)
    st.divider()
    st.info("🧿 V197 THE INSTINCT: 'Survival Mode' (Küme Düşme Motivasyonu) ve Ekstrem Gol Pazarları entegre edildi.")

st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:48px;'>🧿 QUANTUM ORACLE V197</h1>", unsafe_allow_html=True)

# --- ORAN GİRİŞ ALANI (V197 GÜNCEL) ---
st.markdown("<div class='api-box'>", unsafe_allow_html=True)
c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1, 1.2])
with c1:
    st.markdown("<h4>📊 Taraf</h4>", unsafe_allow_html=True)
    ms1 = st.number_input("MS 1", value=st.session_state.ms1, format="%.2f")
    msx = st.number_input("MS X", value=st.session_state.msx, format="%.2f")
    ms2 = st.number_input("MS 2", value=st.session_state.ms2, format="%.2f")
with c2:
    st.markdown("<h4>⚽ Alt/Üst</h4>", unsafe_allow_html=True)
    o15 = st.number_input("1.5 ÜST", value=st.session_state.o15, format="%.2f")
    o25 = st.number_input("2.5 ÜST", value=st.session_state.o25, format="%.2f")
    o35 = st.number_input("3.5 ÜST", value=st.session_state.o35, format="%.2f")
with c3:
    st.markdown("<h4>⚽ Diğer</h4>", unsafe_allow_html=True)
    u25 = st.number_input("2.5 ALT", value=st.session_state.u25, format="%.2f")
    kgv = st.number_input("KG VAR", value=st.session_state.btts_y, format="%.2f")
    kgy = st.number_input("KG YOK", value=st.session_state.btts_n, format="%.2f")
with c4:
    st.markdown("<h4>🌍 Takımlar</h4>", unsafe_allow_html=True)
    ev_t = st.text_input("Ev Sahibi", value=st.session_state.ev_t)
    dep_t = st.text_input("Deplasman", value=st.session_state.dep_t)
with c5:
    st.markdown("<h4>⚙️ Havuz</h4>", unsafe_allow_html=True)
    sec_lig = st.selectbox("Lig Seçimi", mevcut_ligler)
    fetch_btn = st.button("🚀 MAÇLARI GETİR (API)")
st.markdown("</div>", unsafe_allow_html=True)

# Helper functions
def get_clean_team_name(t):
    t = str(t).lower().strip()
    aliases = {"atletico madrid": "Ath Madrid", "arsenal": "Arsenal", "leverkusen": "Leverkusen", "bayern": "Bayern Munich"}
    for k, v in aliases.items():
        if k in t: return v
    return t.title()

def get_recent_stats(name, df):
    m = df[(df['HomeTeam'].str.contains(name, case=False, na=False)) | (df['AwayTeam'].str.contains(name, case=False, na=False))].tail(5)
    if m.empty: return 0,0,0,0,0
    pts = 0
    for _, r in m.iterrows():
        is_h = name.lower() in str(r['HomeTeam']).lower()
        if (is_h and r['FTR']=='H') or (not is_h and r['FTR']=='A'): pts += 3
        elif r['FTR']=='D': pts += 1
    return pts, m['FTHG'].sum(), m['FTAG'].sum(), len(m), pts/len(m)

if st.button("🚀 TAM OTONOM YAPAY ZEKAYI BAŞLAT"):
    aktif_db = db.copy()
    lig_kodu = sec_lig.split(" | ")[0] if " | " in sec_lig else None
    dna = LEAGUE_DNA.get(lig_kodu, {'card_mod':1.0, 'xg_mod':1.0, 'corner_mod':1.0})
    
    ev_pts, ev_gs, ev_gc, ev_gp, ev_ppg = get_recent_stats(ev_t, aktif_db)
    dep_pts, dep_gs, dep_gc, dep_gp, dep_ppg = get_recent_stats(dep_t, aktif_db)

    # --- V197 SURVIVAL MODE (CAN HAVLİ) ALGORİTMASI ---
    is_survival = False
    survival_boost = 1.0
    current_month = datetime.datetime.now().month
    # Mart, Nisan, Mayıs aylarındaysak ve bir takımın puanı çok düşükse (düşme potası)
    if current_month in [3, 4, 5]:
        if (ev_ppg < 1.0 and dep_ppg > 1.8) or (dep_ppg < 1.0 and ev_ppg > 1.8):
            is_survival = True
            survival_boost = 1.25 # %25 Motivasyon Artışı

    if is_survival:
        st.markdown(f"<div class='survival-mode'>🚨 SURVIVAL MODE AKTİF: Küme düşme savaşı veren takımın motivasyon çarpanı ({survival_boost}x) analize eklendi!</div>", unsafe_allow_html=True)

    # İstatistiki Hesaplamalar
    true_ev_xg = (ev_gs/max(ev_gp,1) * survival_boost) * dna['xg_mod']
    true_dep_xg = (dep_gs/max(dep_gp,1) * survival_boost) * dna['xg_mod']

    # Benzer Maç Bulma
    aktif_db['diff'] = np.sqrt((aktif_db['B365H']-ms1)**2 + (aktif_db['B365A']-ms2)**2)
    benzer = aktif_db.sort_values('diff').head(75)
    
    # Oran Hesaplama
    p_ms1 = (benzer['FTR']=='H').mean() * 100
    p_msx = (benzer['FTR']=='D').mean() * 100
    p_ms2 = (benzer['FTR']=='A').mean() * 100
    p_o25 = ((benzer['FTHG'] + benzer['FTAG']) > 2.5).mean() * 100
    p_o15 = ((benzer['FTHG'] + benzer['FTAG']) > 1.5).mean() * 100
    p_o35 = ((benzer['FTHG'] + benzer['FTAG']) > 3.5).mean() * 100

    # UI Çıktıları
    st.markdown("<h2>📊 Olasılık Matrisi</h2>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    with c1: st.markdown(f"<div class='prob-card' style='border-top:5px solid #00ffcc;'><span class='prob-title'>MS 1</span><div class='prob-value'>%{int(p_ms1)}</div><div class='prob-odd'>{ms1}</div></div>", unsafe_allow_html=True)
    with c2: st.markdown(f"<div class='prob-card' style='border-top:5px solid #d4af37;'><span class='prob-title'>1.5 ÜST</span><div class='prob-value'>%{int(p_o15)}</div><div class='prob-odd'>{o15}</div></div>", unsafe_allow_html=True)
    with c3: st.markdown(f"<div class='prob-card' style='border-top:5px solid #ffcc00;'><span class='prob-title'>2.5 ÜST</span><div class='prob-value'>%{int(p_o25)}</div><div class='prob-odd'>{o25}</div></div>", unsafe_allow_html=True)
    with c4: st.markdown(f"<div class='prob-card' style='border-top:5px solid #ff4b4b;'><span class='prob-title'>3.5 ÜST</span><div class='prob-value'>%{int(p_o35)}</div><div class='prob-odd'>{o35}</div></div>", unsafe_allow_html=True)

    # Value Alarm Sistemi
    v_alarms = []
    for p_name, p_val, p_odd in [("MS 1", p_ms1, ms1), ("1.5 ÜST", p_o15, o15), ("2.5 ÜST", p_o25, o25), ("3.5 ÜST", p_o35, o35)]:
        implied = (1/p_odd)*100
        if (p_val - implied) >= value_threshold: v_alarms.append(f"{p_name} (Sistem: %{int(p_val)} / Şirket: %{int(implied)})")
    
    if v_alarms:
        st.markdown(f"<div class='value-alarm'><h2>🚨 DEĞERLİ ORAN BULUNDU!</h2><b>{'<br>'.join(v_alarms)}</b></div>", unsafe_allow_html=True)

    # Poisson İlk Yarı Analizi (HT SNIPER)
    match_ht_xg = (true_ev_xg + true_dep_xg) / 2.5
    prob_ht_o15 = (1 - (poisson.pmf(0, match_ht_xg) + poisson.pmf(1, match_ht_xg))) * 100
    
    st.markdown("<div class='alt-market'>", unsafe_allow_html=True)
    st.markdown(f"<h3>⏱️ İ.Y 1.5 Üst Poisson Radarı: <span style='color:#00ffcc;'>%{int(prob_ht_o15)}</span></h3>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # xG Paneli
    st.markdown(f"<div style='background:#121820; padding:30px; border-radius:15px; border-left:6px solid #8a2be2;'><h3>⚽ Gerçek xG Çarpışması</h3>Ev: {true_ev_xg:.2f} | Dep: {true_dep_xg:.2f} | Toplam: {(true_ev_xg+true_dep_xg):.2f}</div>", unsafe_allow_html=True)

    # Zaman Makinesi
    st.divider()
    sim_df = benzer.head(30)
    kasa = 0
    kasa_yol = [0]
    for _, r in sim_df.iterrows():
        if r['FTHG']+r['FTAG'] > 2.5: kasa += (100*r['B365O'])-100
        else: kasa -= 100
        kasa_yol.append(kasa)
    st.line_chart(kasa_yol)
