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

# --- QUANTUM DESIGN: V198 THE ARCHITECT (FIXED CRASH & TOTAL GRID UI) ---
st.set_page_config(page_title="V198 | QUANTUM APEX", layout="wide", page_icon="💎")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    
    /* Font Büyütme Operasyonu */
    p, span, label { font-size: 16px !important; font-weight: 600 !important; }
    .stNumberInput label { font-size: 18px !important; color: #d4af37 !important; }
    
    div.stButton > button:first-child { 
        background: linear-gradient(90deg, #d4af37, #ffcc00); color:black; border:none; 
        font-weight:900; font-size: 20px; height: 3.5em; width: 100%; 
        box-shadow: 0 6px 20px rgba(212, 175, 55, 0.5); text-transform: uppercase; border-radius: 12px;
    }
    
    .input-container { background: #0c1015; border: 1px solid #1e2530; padding: 25px; border-radius: 15px; margin-bottom: 20px; }
    .header-box { background: linear-gradient(90deg, #0f2027, #203a43); padding: 20px; border-radius: 15px; border-left: 8px solid #d4af37; margin-bottom: 25px; }
    .ai-verdict-box { background: linear-gradient(145deg, #0a0a0a, #151100); border: 2px solid #d4af37; padding: 35px; border-radius: 20px; text-align: center; }
    .prob-card { background: #0c1015; border-radius: 15px; padding: 25px 15px; text-align: center; border: 1px solid #1e2530; margin-bottom: 15px; }
    .prob-value { font-size: 42px; font-weight: 900; }
    .survival-mode { background: linear-gradient(90deg, #ff4b4b, #800000); padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #fff; font-size: 20px !important; font-weight: 900 !important; }
    </style>
    """, unsafe_allow_html=True)

# --- VERİ ÇEKME VE HAZIRLIK ---
LIG_MAP = {
    'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'E1': 'İngiltere Championship',
    'SP1': 'İspanya La Liga 1', 'I1': 'İtalya Serie A', 'D1': 'Almanya Bundesliga 1', 'F1': 'Fransa Ligue 1'
}

@st.cache_data(ttl=3600)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223']
    leagues = list(LIG_MAP.keys())
    dfs = []
    for s in seasons:
        for l in leagues:
            try:
                url = f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv'
                df = pd.read_csv(url)
                if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
                cols = ['Div','Date','HomeTeam','AwayTeam','B365H','B365D','B365A','B365O','B365U','FTR','FTHG','FTAG','HTHG','HTAG']
                df = df[[c for c in cols if c in df.columns]].dropna(subset=['B365H'])
                df['Season'] = s
                dfs.append(df)
            except: continue
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

db = load_quantum_data()

# --- HATA DÜZELTME: mevcut_ligler her zaman en başta tanımlanmalı ---
mevcut_ligler = ["TÜM DÜNYA (GLOBAL)"]
if not db.empty:
    mevcut_ligler += sorted([f"{k} | {v}" for k, v in LIG_MAP.items() if k in db['Div'].unique()])

# Session State
defaults = {'ms1':2.10, 'msx':3.30, 'ms2':3.40, 'o15':1.25, 'u15':3.50, 'o25':1.90, 'u25':1.90, 'o35':3.20, 'u35':1.30, 'kgv':1.70, 'kgy':2.00, 'ev_t':'Ev Sahibi', 'dep_t':'Deplasman'}
for k, v in defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# --- ARAYÜZ BAŞLIĞI ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:54px;'>💎 QUANTUM ORACLE V198</h1>", unsafe_allow_html=True)

# --- ÜST PANEL: TAKIM VE LİG SEÇİMİ ---
st.markdown("<div class='header-box'>", unsafe_allow_html=True)
top_c1, top_c2, top_c3 = st.columns([1.5, 1.5, 1.5])
with top_c1: ev_t = st.text_input("🏠 EV SAHİBİ TAKIM", value=st.session_state.ev_t)
with top_c2: dep_t = st.text_input("🚀 DEPLASMAN TAKIM", value=st.session_state.dep_t)
with top_c3: sec_lig = st.selectbox("🌍 ANALİZ EDİLECEK LİG", mevcut_ligler)
st.markdown("</div>", unsafe_allow_html=True)

# --- ANA GİRİŞ PANELİ: DÜZENLİ GRID SİSTEMİ ---
st.markdown("<div class='input-container'>", unsafe_allow_html=True)
col_ms, col_uo, col_kg = st.columns([1, 2, 1])

with col_ms:
    st.markdown("<h3 style='color:#00ffcc;'>📊 TARAF ORANLARI</h3>", unsafe_allow_html=True)
    ms1 = st.number_input("MS 1", value=st.session_state.ms1, format="%.2f")
    msx = st.number_input("MS X", value=st.session_state.msx, format="%.2f")
    ms2 = st.number_input("MS 2", value=st.session_state.ms2, format="%.2f")

with col_uo:
    st.markdown("<h3 style='color:#00ffcc;'>⚽ ALT / ÜST ORANLARI</h3>", unsafe_allow_html=True)
    uo1, uo2 = st.columns(2)
    with uo1:
        o15 = st.number_input("1.5 ÜST", value=st.session_state.o15, format="%.2f")
        o25 = st.number_input("2.5 ÜST", value=st.session_state.o25, format="%.2f")
        o35 = st.number_input("3.5 ÜST", value=st.session_state.o35, format="%.2f")
    with uo2:
        u15 = st.number_input("1.5 ALT", value=st.session_state.u15, format="%.2f")
        u25 = st.number_input("2.5 ALT", value=st.session_state.u25, format="%.2f")
        u35 = st.number_input("3.5 ALT", value=st.session_state.u35, format="%.2f")

with col_kg:
    st.markdown("<h3 style='color:#00ffcc;'>🎯 KG VAR/YOK</h3>", unsafe_allow_html=True)
    kgv = st.number_input("KG VAR", value=st.session_state.kgv, format="%.2f")
    kgy = st.number_input("KG YOK", value=st.session_state.kgy, format="%.2f")
    st.markdown("<br>", unsafe_allow_html=True)
    with st.sidebar:
        value_threshold = st.slider("🚨 Value Hassasiyeti (%)", 3, 25, 10)
st.markdown("</div>", unsafe_allow_html=True)

# Helper functions
def get_recent_stats(name, df):
    m = df[(df['HomeTeam'].str.contains(name, case=False, na=False)) | (df['AwayTeam'].str.contains(name, case=False, na=False))].tail(5)
    if m.empty: return 0,0,0,0,0
    pts = 0
    for _, r in m.iterrows():
        is_h = name.lower() in str(r['HomeTeam']).lower()
        if (is_h and r['FTR']=='H') or (not is_h and r['FTR']=='A'): pts += 3
        elif r['FTR']=='D': pts += 1
    return pts, m['FTHG'].sum(), m['FTAG'].sum(), len(m), pts/len(m)

if st.button("🚀 ANALİZİ VE SİMÜLASYONU BAŞLAT"):
    with st.spinner("V198 ARCHITECT: Veriler işleniyor, hayalet simülasyonu devrede..."):
        # Survival Mode Logic
        ev_pts, ev_gs, ev_gc, ev_gp, ev_ppg = get_recent_stats(ev_t, db)
        dep_pts, dep_gs, dep_gc, dep_gp, dep_ppg = get_recent_stats(dep_t, db)
        
        is_survival = False
        survival_boost = 1.0
        if datetime.datetime.now().month in [3, 4, 5]:
            if (ev_ppg < 1.0 and dep_ppg > 1.8) or (dep_ppg < 1.0 and ev_ppg > 1.8):
                is_survival = True
                survival_boost = 1.25

        if is_survival:
            st.markdown(f"<div class='survival-mode'>🚨 SURVIVAL MODE: Düşme potasındaki takımın can havli motivasyonu eklendi!</div>", unsafe_allow_html=True)

        # Benzer Maçlar
        db['diff'] = np.sqrt((db['B365H']-ms1)**2 + (db['B365A']-ms2)**2)
        benzer = db.sort_values('diff').head(75)
        
        # Olasılıklar
        p_ms1 = (benzer['FTR']=='H').mean() * 100
        p_msx = (benzer['FTR']=='D').mean() * 100
        p_ms2 = (benzer['FTR']=='A').mean() * 100
        p_o25 = ((benzer['FTHG'] + benzer['FTAG']) > 2.5).mean() * 100
        p_u25 = 100 - p_o25
        p_o15 = ((benzer['FTHG'] + benzer['FTAG']) > 1.5).mean() * 100
        p_o35 = ((benzer['FTHG'] + benzer['FTAG']) > 3.5).mean() * 100

        # SONUÇ EKRANI
        res_c1, res_c2, res_c3 = st.columns(3)
        with res_c1: st.markdown(f"<div class='prob-card' style='border-top:5px solid #00ffcc;'><span style='color:#8b949e;'>MS 1 ŞANSI</span><div class='prob-value' style='color:#00ffcc;'>%{int(p_ms1)}</div></div>", unsafe_allow_html=True)
        with res_c2: st.markdown(f"<div class='prob-card' style='border-top:5px solid #ffcc00;'><span style='color:#8b949e;'>2.5 ÜST ŞANSI</span><div class='prob-value' style='color:#ffcc00;'>%{int(p_o25)}</div></div>", unsafe_allow_html=True)
        with res_c3: st.markdown(f"<div class='prob-card' style='border-top:5px solid #ff4b4b;'><span style='color:#8b949e;'>MS 2 ŞANSI</span><div class='prob-value' style='color:#ff4b4b;'>%{int(p_ms2)}</div></div>", unsafe_allow_html=True)

        # VALUE ALARMLARI (Hata Payı Tespiti)
        st.markdown("<h2>🚨 SİSTEM AÇIĞI (VALUE) ANALİZİ</h2>", unsafe_allow_html=True)
        v_list = []
        for n, p, o in [("MS 1", p_ms1, ms1), ("MS 2", p_ms2, ms2), ("2.5 ÜST", p_o25, o25), ("1.5 ÜST", p_o15, o15), ("3.5 ÜST", p_o35, o35)]:
            if (p - (1/o*100)) >= value_threshold: v_list.append(f"💎 {n} Oranında Devasa Değer!")
        
        if v_list:
            st.warning("\n".join(v_list))
        else:
            st.info("Bu maçın oranları tarihsel verilere göre dengeli açılmış, tuzak tespit edilmedi.")

        # xG ve Poisson Detayı
        match_xg = (ev_gs/max(ev_gp,1) + dep_gs/max(dep_gp,1)) * survival_boost
        prob_ht_o15 = (1 - (poisson.pmf(0, match_xg/2.5) + poisson.pmf(1, match_xg/2.5))) * 100
        
        st.markdown(f"<div class='ai-verdict-box'><h3>🎯 OTONOM BANKO: {'2.5 ÜST' if p_o25 > 55 else 'SÜRPRİZ MS 1' if p_ms1 > 40 else 'KG VAR'}</h3><p>İ.Y 1.5 ÜST Olasılığı: %{int(prob_ht_o15)}</p></div>", unsafe_allow_html=True)
