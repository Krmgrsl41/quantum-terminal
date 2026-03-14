import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import requests
import io

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

# --- V1601 KARNELİ RADAR: SAF VERİ + YAPAY ZEKA İSTATİSTİK PANELİ ---
st.set_page_config(page_title="V1601 SAF VERİ RADARI", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #00ffcc; margin: 10px 0; text-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #00ffcc; padding: 25px; border-radius: 12px; margin-top: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    .target-market { color: #000; font-weight: 900; font-size: 22px; background: #00ffcc; padding: 8px 15px; border-radius: 8px; display: inline-block; margin-top: 10px; box-shadow: 0 0 10px rgba(0,255,204,0.3);}
    
    .ai-report { background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); border: 1px solid #2d3748; border-top: 3px solid #00ffcc; padding: 25px; margin-top: 20px; border-radius: 10px; font-size: 16px; line-height: 1.7; color: #e2e8f0; }
    .highlight-gold { color: #ffcc00; font-weight: 900; font-size: 17px;}
    .highlight-green { color: #00ffcc; font-weight: 900; font-size: 17px;}
    .manual-panel { background: #11161d; border: 1px dashed #4a5568; padding: 20px; border-radius: 10px; margin-top: 15px; }
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

API_LEAGUES = {"İngiltere Premier Lig": "soccer_epl", "Almanya Bundesliga": "soccer_germany_bundesliga", "Türkiye Süper Lig": "soccer_turkey_super_league", "Hollanda Eredivisie": "soccer_netherlands_eredivisie", "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a", "Fransa Ligue 1": "soccer_france_ligue_one", "Belçika Pro Lig": "soccer_belgium_first_division_a"}

@st.cache_data(ttl=3600, show_spinner=False)
def load_historical_odds():
    urls = [f'https://www.football-data.co.uk/mmz4281/2425/E0.csv', f'https://www.football-data.co.uk/mmz4281/2324/E0.csv', f'https://www.football-data.co.uk/mmz4281/2425/T1.csv', f'https://www.football-data.co.uk/mmz4281/2324/T1.csv']
    dfs = []
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                if 'B365H' in df.columns: dfs.append(df[['B365H', 'B365D', 'B365A', 'FTR', 'FTHG', 'FTAG', 'HTHG', 'HTAG']].dropna())
        except: pass
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

db_odds = load_historical_odds()

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
                    elif "Korner" in target_market: return "BEKLİYOR", "Korner Manuel" 
                    
                    return ("KAZANDI" if won else "KAYBETTİ"), f"{h_score}-{a_score}"
        return "BEKLİYOR", "Maç Bitmedi"
    except: return "BEKLİYOR", "Hata"

# --- ARAYÜZ ---
st.markdown("<h1 style='text-align:center; color:#00ffcc; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(0,255,204,0.3);'>🎯 V1601 SAF VERİ RADARI</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>Sıfır Manipülasyon | Çıplak İstatistik | Otonom Öğrenme Raporu</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📡 1. MAÇLARI ÇEK", "🔬 2. ANALİZ VE VUR-KAÇ", "💼 3. BİLANÇO MUHASEBESİ"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Ligleri Seçin:", list(API_LEAGUES.keys()), default=["İngiltere Premier Lig", "Türkiye Süper Lig", "Almanya Bundesliga"])
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
                st.success(f"✅ Toplam {len(toplanan_maclar)} maç çekildi. 2. Sekmeye geçin.")

with tab2:
    if len(st.session_state.raw_api_data) == 0:
        st.info("Lütfen 1. Sekmeden maçları çekin.")
    else:
        mac_isimleri = [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
        secilen_mac_str = st.selectbox("🎯 Analiz Edilecek Maçı Seçin:", mac_isimleri)
        
        if secilen_mac_str:
            secilen_mac = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str)
            
            st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color:#00ffcc;'>⚙️ Saf İstihbarat Verisi (Sadece Rakamlar)</h3>", unsafe_allow_html=True)
            st.markdown("<i style='color:#8b949e;'>Makinenin suni torpil yapmasını engellemek için sıralama verisi kaldırılmıştır. Sadece attığı/yediği maç verisini giriniz.</i><br><br>", unsafe_allow_html=True)
            
            guven_esigi = st.slider("Güvenlik Eşiği Belirle (%):", min_value=50, max_value=90, value=65, step=1)
            st.divider()

            c_ev, c_dep = st.columns(2)
            with c_ev:
                st.markdown(f"**🏠 {secilen_mac['home_team']} (Ev Sahibi)**")
                ev_mac = st.number_input("Oynadığı Maç:", min_value=1, value=29, key="ev_mac")
                ev_at = st.number_input("Attığı Gol:", min_value=0, value=60, key="ev_at")
                ev_ye = st.number_input("Yediği Gol:", min_value=0, value=18, key="ev_ye")
                ev_kor_kul = st.number_input("Ort. Korner:", min_value=0.0, value=6.0, step=0.5, key="ev_kor_kul")
                
            with c_dep:
                st.markdown(f"**✈️ {secilen_mac['away_team']} (Deplasman)**")
                dep_mac = st.number_input("Oynadığı Maç:", min_value=1, value=29, key="dep_mac")
                dep_at = st.number_input("Attığı Gol:", min_value=0, value=40, key="dep_at")
                dep_ye = st.number_input("Yediği Gol:", min_value=0, value=35, key="dep_ye")
                dep_kor_kul = st.number_input("Ort. Korner:", min_value=0.0, value=4.5, step=0.5, key="dep_kor_kul")
            
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if st.button("☢️ SAF VERİ İLE ANALİZİ BAŞLAT", use_container_width=True):
                with st.spinner("Çıplak verilerle matris çiziliyor, manipülasyonlar silindi..."):
                    
                    h_odd, d_odd, a_odd = 2.50, 3.20, 2.80 
                    api_basarili = False
                    
                    try:
                        for bkm in secilen_mac.get('bookmakers', []):
                            for mkt in bkm.get('markets', []):
                                if mkt['key'] == 'h2h':
                                    for out in mkt['outcomes']:
                                        out_name = str(out['name']).lower()
                                        home_name = str(secilen_mac['home_team']).lower()
                                        away_name = str(secilen_mac['away_team']).lower()
                                        
                                        if out_name in home_name or home_name in out_name: 
                                            h_odd = out['price']
                                            api_basarili = True
                                        elif out_name in away_name or away_name in out_name: 
                                            a_odd = out['price']
                                        elif out_name == 'draw': 
                                            d_odd = out['price']
                    except: pass

                    # MOTOR A: SAF POISSON
                    ev_atk_ort = ev_at / ev_mac if ev_mac > 0 else 1.0
                    ev_def_ort = ev_ye / ev_mac if ev_mac > 0 else 1.0
                    dep_atk_ort = dep_at / dep_mac if dep_mac > 0 else 1.0
                    dep_def_ort = dep_ye / dep_mac if dep_mac > 0 else 1.0
                    
                    lambda_home = max(0.1, (ev_atk_ort + dep_def_ort) / 2.0)
                    lambda_away = max(0.1, (dep_atk_ort + ev_def_ort) / 2.0)
                    
                    lambda_ht_home = lambda_home * 0.45
                    lambda_ht_away = lambda_away * 0.45

                    p_ms1=0.0; p_ms2=0.0; p_ms0=0.0
                    p_15ust=0.0; p_25ust=0.0; p_35ust=0.0
                    p_kgvar=0.0; p_iy15ust=0.0; p_korner95ust=0.0; p_korner85ust=0.0

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
                            
                    for h in range(4):
                        for a in range(4):
                            prob = poisson.pmf(h, lambda_ht_home) * poisson.pmf(a, lambda_ht_away)
                            if (h + a) > 1.5: p_iy15ust += prob
                            
                    for h in range(16):
                        for a in range(16):
                            prob = poisson.pmf(h, ev_kor_kul) * poisson.pmf(a, dep_kor_kul)
                            if (h + a) > 8.5: p_korner85ust += prob
                            if (h + a) > 9.5: p_korner95ust += prob

                    poisson_olasiliklar = {
                        "MS 1": p_ms1, "MS 2": p_ms2, "MS 0": p_ms0,
                        "1.5 Üst": p_15ust, "2.5 Üst": p_25ust, "2.5 Alt": (1-p_25ust),
                        "3.5 Üst": p_35ust, "3.5 Alt": (1-p_35ust),
                        "KG Var": p_kgvar, "KG Yok": (1-p_kgvar),
                        "İY 1.5 Üst": p_iy15ust, "İY 1.5 Alt": (1-p_iy15ust),
                        "Korner 8.5 Üst": p_korner85ust, "Korner 9.5 Üst": p_korner95ust
                    }

                    oranexcel_olasiliklar = {k: 0.50 for k in poisson_olasiliklar.keys()} 
                    if len(db_odds) > 50:
                        benzerler = db_odds[(db_odds['B365H'] >= h_odd - 0.15) & (db_odds['B365H'] <= h_odd + 0.15)]
                        if len(benzerler) > 20:
                            oranexcel_olasiliklar["MS 1"] = (benzerler['FTR'] == 'H').mean()
                            oranexcel_olasiliklar["MS 2"] = (benzerler['FTR'] == 'A').mean()
                            oranexcel_olasiliklar["MS 0"] = (benzerler['FTR'] == 'D').mean()
                            
                            toplam_goller = benzerler['FTHG'] + benzerler['FTAG']
                            oranexcel_olasiliklar["1.5 Üst"] = (toplam_goller > 1.5).mean()
                            oranexcel_olasiliklar["2.5 Üst"] = (toplam_goller > 2.5).mean()
                            oranexcel_olasiliklar["2.5 Alt"] = 1 - oranexcel_olasiliklar["2.5 Üst"]
                            oranexcel_olasiliklar["3.5 Üst"] = (toplam_goller > 3.5).mean()
                            oranexcel_olasiliklar["3.5 Alt"] = 1 - oranexcel_olasiliklar["3.5 Üst"]
                            
                            oranexcel_olasiliklar["KG Var"] = ((benzerler['FTHG'] > 0) & (benzerler['FTAG'] > 0)).mean()
                            oranexcel_olasiliklar["KG Yok"] = 1 - oranexcel_olasiliklar["KG Var"]
                            
                            iy_goller = benzerler['HTHG'] + benzerler['HTAG']
                            oranexcel_olasiliklar["İY 1.5 Üst"] = (iy_goller > 1.5).mean()
                            oranexcel_olasiliklar["İY 1.5 Alt"] = 1 - oranexcel_olasiliklar["İY 1.5 Üst"]
                            
                            oranexcel_olasiliklar["Korner 8.5 Üst"] = poisson_olasiliklar["Korner 8.5 Üst"] 
                            oranexcel_olasiliklar["Korner 9.5 Üst"] = poisson_olasiliklar["Korner 9.5 Üst"]

                    fuzyon_sonuclar = []
                    for pazar in poisson_olasiliklar.keys():
                        ort_ihtimal = (poisson_olasiliklar[pazar] + oranexcel_olasiliklar[pazar]) / 2.0
                        fuzyon_sonuclar.append((pazar, ort_ihtimal, poisson_olasiliklar[pazar], oranexcel_olasiliklar[pazar]))

                    THRESHOLD = guven_esigi / 100.0
                    gecen_hedefler = sorted([h for h in fuzyon_sonuclar if h[1] >= THRESHOLD], key=lambda x: x[1], reverse=True)
                    
                    if len(gecen_hedefler) > 0:
                        rapor = f"🔥 <b>V1601 SAF VERİ RADARI ÇALIŞTI!</b><br><br>"
                        
                        if api_basarili:
                            rapor += f"📡 <span style='color:#00ffcc;'>API BAZLI RÖNTGEN BAŞARILI:</span> Sistem, İddaa'nın açtığı güncel taraf oranlarını (Ev: <b>{h_odd:.2f}</b>) yakaladı ve Oranexcel'i bu gerçek değere göre süzdü.<br><br>"
                        else:
                            rapor += f"📡 <span style='color:#ff4b4b;'>API KÖRLÜK UYARISI:</span> API bu maça ait güncel oranları çekemedi. Sistem güvenlik gereği Ev Sahibi Oranını varsayılan olarak (<b>2.50</b>) baz aldı. <i>(Lütfen sonuçları buna göre değerlendirin).</i><br><br>"

                        rapor += f"Eşiği (%{guven_esigi}) geçmeyi başaran <b>TÜM PAZARLAR</b> sadece senin girdiğin net gol/korner rakamlarına göre (Sıfır Manipülasyon) hesaplanmış ve en yüksek ihtimalden en düşüğe doğru aşağıda listelenmiştir.<br><br>"
                        
                        for i, hedef in enumerate(gecen_hedefler):
                            pazar, final_prob, p_prob, o_prob = hedef
                            adil_oran = 1.0 / final_prob if final_prob > 0 else 0
                            
                            if i == 0:
                                rapor += f"🥇 <span class='highlight-gold'><b>[{pazar}]</b></span> -> İhtimal: <span class='highlight-green'>%{int(final_prob*100)}</span> | Adil Oran: <b>{adil_oran:.2f}</b><br>"
                            else:
                                rapor += f"• <b>[{pazar}]</b> -> İhtimal: %{int(final_prob*100)} | Adil Oran: {adil_oran:.2f}<br>"

                        secilen_mac['gecen_hedefler'] = gecen_hedefler
                        secilen_mac['ai_rapor'] = rapor
                        
                        st.session_state.aktif_mac = secilen_mac 
                        st.success(f"☢️ Hedefler Bulundu! Saf veriyle hesaplandı.")
                    else:
                        st.session_state.aktif_mac = None
                        st.error(f"🚨 UYARI: Verilere göre hiçbir ihtimal %{guven_esigi} barajını geçemedi. Pas geçin.")

        if 'aktif_mac' in st.session_state and st.session_state.aktif_mac is not None:
            m = st.session_state.aktif_mac
            st.divider()
            
            st.markdown(f"<div class='match-card'><div class='match-title'>{m['home_team']} ⚡ {m['away_team']}</div><br>", unsafe_allow_html=True)
            st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div><br>", unsafe_allow_html=True)
            
            hedef_opsiyonlari = [f"{h[0]} (İhtimal: %{int(h[1]*100)} - Adil Oran: {(1/h[1]):.2f})" for h in m['gecen_hedefler']]
            secilen_hedef_str = st.selectbox("📌 KASAYA İŞLENECEK HEDEFİ SEÇİN:", hedef_opsiyonlari, key="nihai_hedef_secim")
            
            nihai_pazar = secilen_hedef_str.split(' (')[0]
            nihai_prob_str = secilen_hedef_str.split('%')[1].split(' ')[0]
            nihai_prob = float(nihai_prob_str) / 100.0
            
            c_oran, c_bos = st.columns([1, 1])
            with c_oran:
                m['manuel_oran'] = st.number_input(f"Seçtiğin [{nihai_pazar}] hedefinin İddaa'daki Gerçek Oranını Girin:", min_value=1.00, value=1.50, step=0.01, key="iddaa_guncel_oran")
            st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("### 🚀 Vur Kaç (Tek İşlem Onayı)")
            manuel_tutar = st.number_input("💵 İşlem Tutarı:", min_value=10.0, value=100.0, step=10.0, key="tutar_tekli")
            
            c_btn_real, c_btn_shadow = st.columns(2)
            with c_btn_real:
                btn_gercek = st.button("🚀 ONAYLA (Gerçek Kasa)", use_container_width=True, key="onay_gercek_tek")
            with c_btn_shadow:
                btn_sanal = st.button("👻 GÖLGE MODU (Eğitim)", use_container_width=True, key="onay_sanal_tek")
                
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
                    
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, m.get('manuel_oran', 1.50), durum_text, "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, oranlar])
                
                st.session_state.aktif_mac = None
                st.success(f"İşlem Başarılı! Seçtiğin [{nihai_pazar}] tahmini sisteme ateşlendi.")
                st.rerun()

with tab3:
    st.markdown("<h2 style='color:#d4af37;'>💼 Kuantum Fon Bilanço Özeti</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    kasa, bekleyen, baslangic = st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa
    roi = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL KASA</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIM</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>ROI (KÂR/ZARAR)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    st.divider()
    
    st.markdown("### 🔄 Manuel Kasa Güncelleme")
    yeni_kasa_tutari = st.number_input("Sisteme yeni bir kasa (sermaye) tutarı tanımlayın:", min_value=0.0, value=float(st.session_state.lokal_kasa), step=100.0, key="yeni_kasa_guncelle")
    if st.button("💾 KASAYI GÜNCELLE", key="btn_kasa_guncelle"):
        st.session_state.lokal_kasa = yeni_kasa_tutari
        if sheet:
            sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 0, 1, "Kasa_Guncellendi", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, "Kasa Yenilendi", "-", "-", "-", "-"])
        st.success("Kasa tutarı başarıyla güncellendi!")
        st.rerun()

    st.divider()
    
    c_btn1, c_btn2 = st.columns([3,1])
    with c_btn1: st.markdown("<h3>📝 Bekleyen Kuponlar</h3>", unsafe_allow_html=True)
    with c_btn2:
        if st.button("🤖 OTONOM DENETÇİYİ ÇALIŞTIR", use_container_width=True, key="otonom_denetci_btn"):
            if not api_key: st.error("API Anahtarı eksik!")
            else:
                with st.spinner("Skorlar denetleniyor, yapay zeka hafızasını güncelliyor..."):
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
                                    res, skor = check_match_result(m_lig, ev, dep, m_pazar, api_key)
                                else:
                                    res, skor = "BEKLİYOR", "Eski Format"
                                    
                                durumlar.append(res)
                                skorlar.append(skor)
                            
                            nihai_sonuc = "BEKLİYOR"
                            if "BEKLİYOR" not in durumlar and "Korner Manuel Denetim" not in skorlar:
                                if "KAYBETTİ" in durumlar: nihai_sonuc = "KAYBETTİ"
                                elif all(d == "KAZANDI" for d in durumlar): nihai_sonuc = "KAZANDI"
                            
                            if nihai_sonuc != "BEKLİYOR":
                                updates_made = True
                                sheet.update_cell(idx+1, 4, "Bekliyor_Kapandı" if not is_sanal else "Sanal_Kapandı")
                                yeni_satir = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), b_tutar, b_oran]
                                
                                if nihai_sonuc == "KAZANDI":
                                    if not is_sanal:
                                        st.session_state.lokal_kasa += (b_tutar * b_oran)
                                        st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                        yeni_satir.extend(["Kazandı_Sonuc", f"+{(b_tutar * b_oran) - b_tutar}"])
                                    else: yeni_satir.extend(["Sanal_Kazandı", "0"]) 
                                else:
                                    if not is_sanal:
                                        st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                        yeni_satir.extend(["Kaybetti_Sonuc", f"-{b_tutar}"])
                                    else: yeni_satir.extend(["Sanal_Kaybetti", "0"]) 
                                    
                                yeni_satir.extend([st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa])
                                yeni_satir.extend([r[8] + f" (Skorlar: {' | '.join(skorlar)})"] + r[9:])
                                sheet.append_row(yeni_satir)
                    if updates_made:
                        st.success("✅ Maçlar sonuçlandırıldı ve veri tabanına işlendi!")
                        st.rerun()
                    else: st.info("Maçlar henüz bitmemiş veya manuel denetim gerektiren pazar (Korner vb.) var.")

    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]]
    if not bekleyenler: st.info("Bekleyen yatırımınız veya sanal eğitim işleminiz yok.")
    else:
        for row_idx, r in bekleyenler:
            is_sanal = (r[3] == "Sanal_Bekliyor")
            b_tutar, b_oran = float(str(r[1]).replace(',','.').strip()), float(str(r[2]).replace(',','.').strip())
            mac_isimleri = r[8].replace('#', ' | ') if len(r) > 10 else "Eski Format"
            border_color = "#4a5568" if is_sanal else "#ff4b4b"
            tutar_text = "<span style='color:#a0aec0;'>0 TL (Sanal)</span>" if is_sanal else f"<span style='color:#00ffcc;'>{b_tutar:.0f} TL</span>"
            st.markdown(f"<div style='background: #11161d; border-left: 4px solid {border_color}; padding:20px; border-radius:10px; margin-bottom:15px;'><b style='font-size:18px;'>Maçlar:</b> <span style='color:#e2e8f0;'>{mac_isimleri}</span><br><br><b style='font-size:16px;'>Tutar:</b> <span style='font-size:18px;'>{tutar_text}</span> &nbsp;|&nbsp; <b style='font-size:16px;'>Oran:</b> <span style='color:#d4af37; font-size:18px; font-weight:bold;'>{b_oran:.2f}</span></div>", unsafe_allow_html=True)

    # --- YENİ EKLENEN YAPAY ZEKA ÖĞRENME İSTATİSTİKLERİ MODÜLÜ ---
    st.divider()
    st.markdown("### 📊 Yapay Zeka Öğrenme İstatistikleri (Analitik Merkezi)")
    
    ai_stats = []
    for r in all_vals:
        if len(r) > 10:
            status = r[3]
            if status in ["Kazandı_Sonuc", "Sanal_Kazandı", "Kaybetti_Sonuc", "Sanal_Kaybetti"]:
                won = status in ["Kazandı_Sonuc", "Sanal_Kazandı"]
                pazarlar = r[10].split('#')
                for p in pazarlar:
                    ai_stats.append({"Pazar": p.strip(), "Sonuc": won})

    if ai_stats:
        df_stats = pd.DataFrame(ai_stats)
        toplam_mac = len(df_stats)
        kazanan = df_stats['Sonuc'].sum()
        kaybeden = toplam_mac - kazanan
        win_rate = (kazanan / toplam_mac) * 100 if toplam_mac > 0 else 0
        
        c_stat1, c_stat2, c_stat3, c_stat4 = st.columns(4)
        c_stat1.metric("Toplam Sonuçlanan", f"{toplam_mac} Maç")
        c_stat2.metric("✅ Başarılı Tahmin", f"{kazanan}")
        c_stat3.metric("❌ Hatalı Tahmin", f"{kaybeden}")
        c_stat4.metric("🎯 Genel İsabet Oranı", f"%{win_rate:.1f}")
        
        st.markdown("#### 🎯 Pazar (Market) Bazlı Analiz Tablosu")
        st.markdown("<i style='color:#8b949e; font-size:14px;'>Aşağıdaki tablo, yapay zekanın geçmişte en çok hangi bahis türlerinde başarılı olduğunu gösterir. Oynayacağınız hedefi seçerken bu tabloyu referans alabilirsiniz.</i><br><br>", unsafe_allow_html=True)
        
        market_stats = df_stats.groupby('Pazar')['Sonuc'].agg(['count', 'sum']).reset_index()
        market_stats.columns = ['Bahis Pazarı', 'Toplam Oynanan', 'Kazanan']
        market_stats['Kaybeden'] = market_stats['Toplam Oynanan'] - market_stats['Kazanan']
        market_stats['İsabet Oranı (%)'] = (market_stats['Kazanan'] / market_stats['Toplam Oynanan']) * 100
        market_stats = market_stats.sort_values(by='İsabet Oranı (%)', ascending=False)
        
        market_stats['İsabet Oranı (%)'] = market_stats['İsabet Oranı (%)'].apply(lambda x: f"%{x:.1f}")
        st.dataframe(market_stats, use_container_width=True, hide_index=True)
    else:
        st.info("Henüz 'Otonom Denetçi' tarafından sonuçlandırılmış ve hafızaya işlenmiş bir maç bulunmuyor. Sanal veya gerçek birkaç maç oynayıp sonuçlandığında tablo burada oluşacaktır.")
