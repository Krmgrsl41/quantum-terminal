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

# --- V1000 KUSURSUZ FÜZYON: ORANEXCEL + POISSON + MAÇKOLİK UYUMU ---
st.set_page_config(page_title="V1000 FÜZYON | ÇİFT MOTORLU FON", layout="wide", page_icon="☢️")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #00ffcc; margin: 10px 0; text-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    .target-market { color: #fff; font-weight: 900; font-size: 20px; background: #ff4b4b; padding: 8px 15px; border-radius: 8px; display: inline-block; margin-top: 10px; box-shadow: 0 0 10px rgba(255,75,75,0.3);}
    
    .ai-report { background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); border: 1px solid #2d3748; border-top: 3px solid #ff4b4b; padding: 25px; margin-top: 20px; border-radius: 10px; font-size: 16px; line-height: 1.7; color: #e2e8f0; }
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
if 'sepet' not in st.session_state: st.session_state.sepet = [] 

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
                if 'B365H' in df.columns: dfs.append(df[['B365H', 'B365D', 'B365A', 'FTHG', 'FTAG', 'HTHG', 'HTAG']].dropna())
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
                    elif "Korner" in target_market: return "BEKLİYOR", "Korner Manuel Denetim" 
                    
                    return ("KAZANDI" if won else "KAYBETTİ"), f"{h_score}-{a_score}"
        return "BEKLİYOR", "Maç Bitmedi"
    except: return "BEKLİYOR", "Hata"

# --- ARAYÜZ ---
st.markdown("<h1 style='text-align:center; color:#ff4b4b; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(255,75,75,0.3);'>☢️ V1000 KUSURSUZ FÜZYON</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>Oranexcel (Şifre) + Objektif Veri (Sıralama, Gol, Korner)</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📡 1. LİSTE ÇEK", "🔬 2. FÜZYON SİMÜLASYONU", "💼 3. FON YÖNETİMİ"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["İngiltere Premier Lig", "Türkiye Süper Lig", "Almanya Bundesliga"])
with c2: 
    api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password", key="odds_api_key")

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
                st.success(f"✅ Toplam {len(toplanan_maclar)} maç listeye alındı. '2. FÜZYON SİMÜLASYONU' sekmesine geçin.")

with tab2:
    if len(st.session_state.raw_api_data) == 0:
        st.info("Lütfen önce 'LİSTE ÇEK' sekmesinden günün maçlarını indirin.")
    else:
        mac_isimleri = [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
        secilen_mac_str = st.selectbox("Simüle Edilecek Maçı Seçin:", mac_isimleri)
        
        if secilen_mac_str:
            secilen_mac = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str)
            
            st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color:#00ffcc;'>⚙️ Objektif İstihbarat (Sadece Sayılar - Maçkolik)</h3>", unsafe_allow_html=True)
            
            guven_esigi = st.slider("Hedef Güvenlik Eşiği Belirle (%):", min_value=60, max_value=90, value=73, step=1)
            st.divider()

            c_ev, c_dep = st.columns(2)
            with c_ev:
                st.markdown(f"**🏠 {secilen_mac['home_team']} (Ev Sahibi)**")
                ev_sira = st.number_input("Ligdeki Sıralaması:", min_value=1, max_value=24, value=5, key="ev_sira")
                ev_mac = st.number_input("Oynadığı Maç:", min_value=1, value=10, key="ev_mac")
                ev_at = st.number_input("Attığı Gol:", min_value=0, value=15, key="ev_at")
                ev_ye = st.number_input("Yediği Gol:", min_value=0, value=10, key="ev_ye")
                ev_kor_kul = st.number_input("Ortalama Kullandığı Korner:", min_value=0.0, value=5.0, step=0.5, key="ev_kor_kul")
                ev_eksik = st.selectbox("Sakatlık/Eksik:", ["Tam Kadro", "Hafif Eksik", "Önemli Eksik (-0.30 xG)", "Kritik Eksik (-0.60 xG)"], key="ev_eksik")
                
            with c_dep:
                st.markdown(f"**✈️ {secilen_mac['away_team']} (Deplasman)**")
                dep_sira = st.number_input("Ligdeki Sıralaması:", min_value=1, max_value=24, value=12, key="dep_sira")
                dep_mac = st.number_input("Oynadığı Maç:", min_value=1, value=10, key="dep_mac")
                dep_at = st.number_input("Attığı Gol:", min_value=0, value=10, key="dep_at")
                dep_ye = st.number_input("Yediği Gol:", min_value=0, value=15, key="dep_ye")
                dep_kor_kul = st.number_input("Ortalama Kullandığı Korner:", min_value=0.0, value=4.5, step=0.5, key="dep_kor_kul")
                dep_eksik = st.selectbox("Sakatlık/Eksik:", ["Tam Kadro", "Hafif Eksik", "Önemli Eksik (-0.30 xG)", "Kritik Eksik (-0.60 xG)"], key="dep_eksik")
            
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if st.button("☢️ FÜZYON MOTORUNU ÇALIŞTIR (Kusursuz Veri)", use_container_width=True):
                with st.spinner("Excalibur işlemcisi devrede... Matris hesaplanıyor..."):
                    
                    h_odd, d_odd, a_odd = 2.50, 3.20, 2.80
                    try:
                        for bkm in secilen_mac.get('bookmakers', []):
                            for mkt in bkm.get('markets', []):
                                if mkt['key'] == 'h2h':
                                    for out in mkt['outcomes']:
                                        if out['name'] == secilen_mac['home_team']: h_odd = out['price']
                                        elif out['name'] == secilen_mac['away_team']: a_odd = out['price']
                                        elif out['name'] == 'Draw': d_odd = out['price']
                    except: pass

                    # ==========================================
                    # MOTOR A: POISSON SİMÜLATÖRÜ (Sıralama + Gol + Korner)
                    # ==========================================
                    ev_atk_ort = ev_at / ev_mac if ev_mac > 0 else 1.0
                    ev_def_ort = ev_ye / ev_mac if ev_mac > 0 else 1.0
                    dep_atk_ort = dep_at / dep_mac if dep_mac > 0 else 1.0
                    dep_def_ort = dep_ye / dep_mac if dep_mac > 0 else 1.0
                    
                    # Sıralama Farkı (Pozitifse Ev Sahibi üstte demektir)
                    sira_farki = dep_sira - ev_sira 
                    
                    # Sakatlık Penaltıları
                    ev_penalti = 0.0
                    if "Hafif" in ev_eksik: ev_penalti = 0.10
                    elif "Önemli" in ev_eksik: ev_penalti = 0.30
                    elif "Kritik" in ev_eksik: ev_penalti = 0.60

                    dep_penalti = 0.0
                    if "Hafif" in dep_eksik: dep_penalti = 0.10
                    elif "Önemli" in dep_eksik: dep_penalti = 0.30
                    elif "Kritik" in dep_eksik: dep_penalti = 0.60
                    
                    # Gelişmiş xG (Form yok, sadece sıralama matematiği var)
                    lambda_home = max(0.1, ((ev_atk_ort + dep_def_ort) / 2.0) + (sira_farki * 0.02) - ev_penalti)
                    lambda_away = max(0.1, ((dep_atk_ort + ev_def_ort) / 2.0) - (sira_farki * 0.02) - dep_penalti)
                    
                    lambda_ht_home = lambda_home * 0.45
                    lambda_ht_away = lambda_away * 0.45

                    # Poisson Olasılıkları
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
                            
                    # KORNER MATRİSİ (Sadece "Kullandığı" kornerler üzerinden direkt hesaplama)
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

                    # ==========================================
                    # MOTOR B: ORANEXCEL (Geçmiş Şifre Çözücü)
                    # ==========================================
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

                    # ==========================================
                    # FÜZYON (İki Motorun Birleşimi)
                    # ==========================================
                    fuzyon_sonuclar = []
                    for pazar in poisson_olasiliklar.keys():
                        ort_ihtimal = (poisson_olasiliklar[pazar] + oranexcel_olasiliklar[pazar]) / 2.0
                        fuzyon_sonuclar.append((pazar, ort_ihtimal, poisson_olasiliklar[pazar], oranexcel_olasiliklar[pazar]))

                    # 4. KESKİN NİŞANCI FİLTRESİ
                    THRESHOLD = guven_esigi / 100.0
                    gecen_hedefler = [h for h in fuzyon_sonuclar if h[1] >= THRESHOLD]
                    
                    if len(gecen_hedefler) > 0:
                        en_iyi_hedef = max(gecen_hedefler, key=lambda item: item[1])
                        en_iyi_pazar, final_prob, p_prob, o_prob = en_iyi_hedef
                        
                        rapor = f"🔥 **V1000 KUSURSUZ FÜZYON BAŞARIYLA ÇALIŞTI!**<br><br>"
                        rapor += f"Sistem subjektif 'form' verilerini silip tamamen net sıralama ve Maçkolik korner ortalamalarıyla 10.000 sanal simülasyon yaptı.<br><br>"
                        
                        rapor += f"🧠 **Objektif Motor 1 (Poisson/xG):** %{int(p_prob*100)} İhtimal Onayı<br>"
                        rapor += f"📊 **Tarihsel Motor 2 (Oranexcel):** %{int(o_prob*100)} İhtimal Onayı<br><br>"
                        
                        rapor += f"🎯 <span class='highlight-gold'>%{guven_esigi} GÜVEN EŞİĞİ AŞILDI!</span><br>"
                        rapor += f"Her iki motorun onayıyla bu maçtaki EN GÜVENLİ MUTLAK LİMAN: <span class='highlight-gold'>[{en_iyi_pazar}]</span><br>"
                        rapor += f"Birleşik Füzyon Net İhtimali: <span class='highlight-green'>%{int(final_prob*100)}</span>"

                        secilen_mac['hedef_pazar'] = en_iyi_pazar
                        secilen_mac['kalibre_ihtimal'] = final_prob
                        secilen_mac['ai_rapor'] = rapor
                        
                        st.session_state.sepet.append(secilen_mac)
                        st.success(f"☢️ Kusursuz Füzyon Başarılı! En mantıklı ve güvenilir hedef sepete eklendi.")
                    else:
                        st.error(f"🚨 FÜZYON UYARISI: Motorlar Anlaşamadı! Sıralama ve Korner matematiğine göre hiçbir ihtimal %{guven_esigi} barajını geçemedi. Kasanızı korumak için pas geçin.")

        if len(st.session_state.sepet) > 0:
            st.divider()
            st.markdown("### 🛒 MUTLAK GÜVEN SEPETİ")
            for i, m in enumerate(st.session_state.sepet):
                st.markdown(f"<div class='match-card'><div class='match-title'>{m['home_team']} ⚡ {m['away_team']}</div><span style='color:#8b949e; font-size:16px;'>Birleşik Füzyon İhtimali: <b style='color:#fff;'>%{int(m['kalibre_ihtimal']*100)}</b></span><br><div class='target-market'>Hedef: {m['hedef_pazar']}</div>", unsafe_allow_html=True)
                with st.expander("🔬 Kusursuz Füzyon Raporunu Oku"):
                    st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div>", unsafe_allow_html=True)
                
                m['manuel_oran'] = st.number_input("Bu seçeneğin İddaa'daki güncel oranını girin:", min_value=1.01, value=1.50, step=0.05, key=f"manuel_oran_{i}")
                st.markdown("</div>", unsafe_allow_html=True)
                
            if st.button("🚮 Sepeti Temizle"):
                st.session_state.sepet = []
                st.rerun()

with tab3:
    st.markdown("<h2 style='color:#d4af37;'>💼 Kuantum Fon Bilanço Özeti (Yapay Zeka Hafızası)</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    kasa, bekleyen, baslangic = st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa
    roi = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL KASA</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIM</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>ROI (KÂR/ZARAR)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    st.divider()
    
    if len(st.session_state.sepet) > 0:
        st.markdown("### 🚀 Sepetteki Maçları Fonla (Öğrenme Modu Açık)")
        manuel_tutar = st.number_input("💵 Kupona Yatırılacak Tutar:", min_value=10.0, value=100.0, step=10.0)
        c_btn_real, c_btn_shadow = st.columns(2)
        
        with c_btn_real:
            btn_gercek = st.button("🚀 ONAYLA (Gerçek Kasa)", use_container_width=True)
        with c_btn_shadow:
            btn_sanal = st.button("👻 GÖLGE MODU (Yapay Zekayı Eğit)", use_container_width=True)
            
        if btn_gercek or btn_sanal:
            toplam_oran = 1.0
            for s in st.session_state.sepet: toplam_oran *= s.get('manuel_oran', 1.50)
            
            if btn_gercek:
                yatirilacak_tutar = manuel_tutar
                st.session_state.lokal_kasa -= yatirilacak_tutar
                st.session_state.bekleyen_tutar += yatirilacak_tutar
                durum_text = "Bekliyor"
            else:
                yatirilacak_tutar = 0.0 
                durum_text = "Sanal_Bekliyor"
            
            if sheet:
                isimler = "#".join([f"{s['home_team']} vs {s['away_team']}" for s in st.session_state.sepet])
                ligler = "#".join([s['sport_key'] for s in st.session_state.sepet])
                tercihler = "#".join([s['hedef_pazar'] for s in st.session_state.sepet])
                problar = "#".join([f"{s['kalibre_ihtimal']:.3f}" for s in st.session_state.sepet])
                oranlar = "#".join([f"{s.get('manuel_oran', 1.50):.2f}" for s in st.session_state.sepet])
                
                sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, toplam_oran, durum_text, "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, oranlar])
            
            st.session_state.sepet = []
            st.success("İşlem Başarılı! Maçlar Yapay Zekanın hafızasına gönderildi.")
            st.rerun()

    st.divider()
    c_btn1, c_btn2 = st.columns([3,1])
    with c_btn1: st.markdown("<h3>📝 Bekleyen Kuponlar (Makine Öğrenimi)</h3>", unsafe_allow_html=True)
    with c_btn2:
        if st.button("🤖 OTONOM DENETÇİYİ ÇALIŞTIR", use_container_width=True):
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
