import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import requests
import io

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    SKLEARN_INSTALLED = True
except ImportError:
    SKLEARN_INSTALLED = False

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

st.set_page_config(page_title="V2300 SKYNET ANALİTİK", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #00ffcc; margin: 10px 0; text-shadow: 0 0 15px rgba(0, 255, 204, 0.3); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #00ffcc; padding: 25px; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    
    .ai-report { background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); border: 1px solid #2d3748; border-top: 3px solid #00ffcc; padding: 25px; margin-top: 20px; border-radius: 10px; font-size: 15px; line-height: 1.6; color: #e2e8f0; }
    .report-card { background: rgba(0,0,0,0.3); border: 1px solid #2d3748; padding: 15px; border-radius: 8px; margin-bottom: 15px; }
    .report-title { color: #00ffcc; font-weight: 900; font-size: 18px; margin-bottom: 5px;}
    
    .manual-panel { background: #11161d; border: 1px dashed #4a5568; padding: 20px; border-radius: 10px; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

if not SKLEARN_INSTALLED:
    st.error("🚨 KRİTİK HATA: Scikit-Learn kütüphanesi eksik! Terminale 'pip install scikit-learn' yazıp kurun.")
    st.stop()

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
    "İngiltere Premier Lig": "soccer_epl", "Türkiye Süper Lig": "soccer_turkey_super_league", 
    "Almanya Bundesliga": "soccer_germany_bundesliga", "İspanya La Liga": "soccer_spain_la_liga",
    "İtalya Serie A": "soccer_italy_serie_a", "Fransa Ligue 1": "soccer_france_ligue_one",
    "Hollanda Eredivisie": "soccer_netherlands_eredivisie", "Belçika Pro Lig": "soccer_belgium_first_division_a"
}

@st.cache_data(ttl=86400, show_spinner=False)
def load_and_train_ml_model():
    leagues_codes = ['E0', 'T1', 'D1', 'SP1', 'I1', 'F1', 'N1', 'B1']
    urls = []
    for code in leagues_codes:
        urls.append(f'https://www.football-data.co.uk/mmz4281/2425/{code}.csv')
        urls.append(f'https://www.football-data.co.uk/mmz4281/2324/{code}.csv')
        
    dfs = []
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                if 'B365H' in df.columns: 
                    dfs.append(df[['B365H', 'B365D', 'B365A', 'FTR', 'FTHG', 'FTAG']].dropna())
        except: pass
    
    if not dfs: return None, None, None, None, None
    df_train = pd.concat(dfs, ignore_index=True)
    
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
    
    rf_taraf.fit(X, y_taraf)
    rf_gol_25.fit(X, y_gol_25)
    rf_gol_15.fit(X, y_gol_15)
    rf_gol_35.fit(X, y_gol_35)
    rf_kg.fit(X, y_kg)
    
    return rf_taraf, rf_gol_25, rf_gol_15, rf_gol_35, rf_kg

model_taraf, model_gol25, model_gol15, model_gol35, model_kg = load_and_train_ml_model()

def check_match_result(sport_key, home, away, target_market, api_key):
    url = f"https://api.the-odds-api.com/v4/sports/{sport_key}/scores/?apiKey={api_key}&daysFrom=3"
    try:
        resp = requests.get(url).json()
        for m in resp:
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
    except: return "BEKLİYOR", "Hata"

# --- ARAYÜZ ---
st.markdown("<h1 style='text-align:center; color:#00ffcc; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(0, 255, 204, 0.4);'>📈 V2300 SKYNET KÂR ANALİTİĞİ</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>Pazar Bazlı ROI (Kâr/Zarar) Tespiti | Oto-Pilot Yatırım Simülatörü</p><br>", unsafe_allow_html=True)

tab1, tab4, tab3 = st.tabs(["📡 1. MAÇLARI ÇEK & OTO-PİLOT", "📈 2. BİLANÇO & KÂR/ZARAR ANALİZİ", "⚙️ MANUEL SİMÜLATÖR (ESKİ)"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Ligleri Seçin:", list(API_LEAGUES.keys()), default=["İngiltere Premier Lig", "Türkiye Süper Lig", "İspanya La Liga"])
with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password", key="odds_api_key")

with tab1:
    if st.button("📡 GÜNÜN MAÇLARINI ÇEK", use_container_width=True):
        if not api_key: st.error("API Anahtarı eksik!")
        else:
            with st.spinner("Piyasadaki oranlar ve maçlar çekiliyor..."):
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
                st.success(f"✅ Toplam {len(toplanan_maclar)} maç çekildi.")

    st.divider()
    st.markdown("### 🤖 SKYNET OTO-PİLOT MODU (Sanal Kasa)")
    st.markdown("<p style='color:#a0aec0;'>Bu mod, günün bütün maçlarını tarar, yapay zekanın güvendiği maçlara <b>sanal olarak 100 TL</b> basarak Excel'e kaydeder. Amacımız hangi bahis türünün daha çok kâr bıraktığını tespit etmektir.</p>", unsafe_allow_html=True)
    
    oto_esik = st.slider("Yapay Zeka Otomatik Onay Eşiği (%):", min_value=50, max_value=90, value=65, step=1)
    
    if st.button("🚀 GÜNÜN TÜM MAÇLARINA OTONOM SANAL YATIRIM YAP", use_container_width=True):
        if len(st.session_state.raw_api_data) == 0:
            st.warning("Önce günün maçlarını çekmelisin!")
        elif model_taraf is None:
            st.error("Makine Öğrenimi aktif değil.")
        else:
            with st.spinner(f"{len(st.session_state.raw_api_data)} maç taranıyor ve sanal portföye ekleniyor..."):
                oto_oynanan_maclar = 0
                
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
                    en_iyi_hedef = None
                    en_yuksek_ihtimal = 0
                    
                    for pazar, prob in ml_probs.items():
                        if prob >= THRESHOLD and prob > en_yuksek_ihtimal:
                            en_yuksek_ihtimal = prob
                            en_iyi_hedef = pazar
                            
                    if en_iyi_hedef and sheet:
                        isimler = f"{m['home_team']} vs {m['away_team']}"
                        ligler = m['sport_key']
                        tercihler = en_iyi_hedef
                        problar = f"{en_yuksek_ihtimal:.3f}"
                        # Gerçek oranları bulalım
                        gercek_oran = 1.50
                        if en_iyi_hedef == "MS 1": gercek_oran = h_odd
                        elif en_iyi_hedef == "MS 0": gercek_oran = d_odd
                        elif en_iyi_hedef == "MS 2": gercek_oran = a_odd
                        
                        # SANAL 100 TL SABİT YATIRIM (Gerçek kasadan düşmez)
                        yatirilacak_tutar = 100.0 
                        durum_text = "Sanal_Bekliyor"
                        
                        sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, f"{gercek_oran:.2f}", durum_text, "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, f"{gercek_oran:.2f}"])
                        oto_oynanan_maclar += 1
                        st.write(f"✅ **{isimler}** ➜ {tercihler} (Oran: {gercek_oran:.2f}) sanal portföye 100 TL ile eklendi.")
                
                if oto_oynanan_maclar > 0:
                    st.success(f"🤖 GÖREV TAMAMLANDI! {oto_oynanan_maclar} maça sanal yatırım yapıldı. Sonuçları 2. Sekmeden takip edebilirsiniz.")
                else:
                    st.warning(f"Sistem %{oto_esik} eşiğini geçen güvenilir bir maç bulamadı.")

with tab4:
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
                with st.spinner("Tüm maç skorları çekiliyor, Kâr/Zarar tabloları güncelleniyor..."):
                    updates_made = False
                    for idx, r in enumerate(all_vals):
                        if len(r) > 12 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]:
                            is_sanal = (r[3] == "Sanal_Bekliyor")
                            b_tutar = float(str(r[1]).replace(',','.'))
                            b_oran = float(str(r[2]).replace(',','.'))
                            
                            maclar = r[8].split('#')
                            ligler = r[9].split('#')
                            pazarlar = r[10].split('#')
                            
                            durumlar = []
                            skorlar = []
                            for m_isim, m_lig, m_pazar in zip(maclar, ligler, pazarlar):
                                if ' vs ' in m_isim:
                                    ev, dep = m_isim.split(' vs ')
                                    res, skor = check_match_result(m_lig, ev, dep, m_pazar.strip(), api_key) 
                                else:
                                    res, skor = "BEKLİYOR", "-"
                                    
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
                        st.success("✅ Maçlar sonuçlandırıldı ve Kâr/Zarar hanesine işlendi!")
                        st.rerun()
                    else: st.info("Maçlar henüz bitmemiş.")

    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]]
    if not bekleyenler: st.info("Bekleyen yatırımınız veya sanal eğitim işleminiz yok.")
    else:
        for row_idx, r in bekleyenler:
            is_sanal = (r[3] == "Sanal_Bekliyor")
            b_tutar, b_oran = float(str(r[1]).replace(',','.').strip()), float(str(r[2]).replace(',','.').strip())
            mac_isimleri = r[8].replace('#', ' | ') if len(r) > 10 else "Eski Format"
            border_color = "#4a5568" if is_sanal else "#00ffcc"
            tutar_text = f"<span style='color:#a0aec0;'>{b_tutar:.0f} TL (Sanal Yatırım)</span>" if is_sanal else f"<span style='color:#00ffcc;'>{b_tutar:.0f} TL (Gerçek)</span>"
            st.markdown(f"<div style='background: #11161d; border-left: 4px solid {border_color}; padding:20px; border-radius:10px; margin-bottom:15px;'><b style='font-size:18px;'>Maçlar:</b> <span style='color:#e2e8f0;'>{mac_isimleri}</span><br><br><b style='font-size:16px;'>Yatırım:</b> <span style='font-size:18px;'>{tutar_text}</span> &nbsp;|&nbsp; <b style='font-size:16px;'>Oran:</b> <span style='color:#d4af37; font-size:18px; font-weight:bold;'>{b_oran:.2f}</span></div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 💎 PAZAR BAZLI KÂR/ZARAR (ROI) ANALİZİ")
    st.markdown("<i style='color:#8b949e; font-size:14px;'>Hangi bahisten para kazanıp hangisinde battığımızı gösteren en kritik tablo. Buradaki veriler sanal ve gerçek yatırımların toplam finansal getirisidir.</i><br><br>", unsafe_allow_html=True)
    
    ai_stats = []
    for r in all_vals:
        if len(r) > 10:
            status = r[3]
            if status in ["Kazandı_Sonuc", "Sanal_Kazandı", "Kaybetti_Sonuc", "Sanal_Kaybetti"]:
                won = status in ["Kazandı_Sonuc", "Sanal_Kazandı"]
                tutar = float(str(r[1]).replace(',','.').strip())
                oran = float(str(r[2]).replace(',','.').strip())
                
                # Eğer eski kayıtlarda tutar 0 ise, hesaplama yapabilmek için varsayılan 100 TL kabul et.
                if tutar == 0: tutar = 100.0 
                
                kar_zarar = (tutar * oran) - tutar if won else -tutar
                
                pazarlar = r[10].split('#')
                for p in pazarlar:
                    pazar_adi = p.strip()
                    if not pazar_adi[0].isdigit() or "Üst" in pazar_adi or "Alt" in pazar_adi or "MS" in pazar_adi:
                        ai_stats.append({"Pazar": pazar_adi, "Sonuc": won, "Yatirim": tutar, "Net_Kar": kar_zarar})

    if ai_stats:
        df_stats = pd.DataFrame(ai_stats)
        
        market_stats = df_stats.groupby('Pazar').agg(
            Toplam_Oynanan=('Sonuc', 'count'),
            Kazanan=('Sonuc', 'sum'),
            Toplam_Yatirim=('Yatirim', 'sum'),
            Net_Kar_Zarar=('Net_Kar', 'sum')
        ).reset_index()
        
        market_stats['Kaybeden'] = market_stats['Toplam_Oynanan'] - market_stats['Kazanan']
        market_stats['İsabet Oranı (%)'] = (market_stats['Kazanan'] / market_stats['Toplam_Oynanan']) * 100
        market_stats['ROI (%) (Kâr Marjı)'] = (market_stats['Net_Kar_Zarar'] / market_stats['Toplam_Yatirim']) * 100
        
        market_stats = market_stats.sort_values(by='Net_Kar_Zarar', ascending=False)
        
        def format_currency(val):
            return f"+{val:.2f} ₺" if val > 0 else f"{val:.2f} ₺"
            
        market_stats['Net_Kar_Zarar'] = market_stats['Net_Kar_Zarar'].apply(format_currency)
        market_stats['İsabet Oranı (%)'] = market_stats['İsabet Oranı (%)'].apply(lambda x: f"%{x:.1f}")
        market_stats['ROI (%) (Kâr Marjı)'] = market_stats['ROI (%) (Kâr Marjı)'].apply(lambda x: f"%{x:.1f}")
        
        # Sütunları düzenle
        market_stats = market_stats[['Bahis Pazarı', 'Toplam_Oynanan', 'Kazanan', 'Kaybeden', 'İsabet Oranı (%)', 'Net_Kar_Zarar', 'ROI (%) (Kâr Marjı)']]
        
        st.dataframe(market_stats, use_container_width=True, hide_index=True)
    else:
        st.info("Finansal analizin oluşması için Otonom Denetçi'nin sonuçlandırdığı maçlar bekleniyor.")

with tab3:
    st.info("Oto-Pilot devrede olduğu için Manuel Simülatör geri plana alınmıştır.")
