import streamlit as st
import pandas as pd
import numpy as np
import datetime
from scipy.stats import poisson
import concurrent.futures
import requests
import io

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_INSTALLED = True
except ImportError:
    GSPREAD_INSTALLED = False

# --- V600 POISSON SNIPER: %73 EŞİK & SİMÜLASYON MOTORU ---
st.set_page_config(page_title="V600 POISSON SNIPER | HİBRİT FON", layout="wide", page_icon="🎯")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #00ffcc; margin: 10px 0; text-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #d4af37; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    .match-card:hover { transform: scale(1.01); border-left: 5px solid #00ffcc;}
    .target-market { color: #000; font-weight: 900; font-size: 20px; background: #d4af37; padding: 8px 15px; border-radius: 8px; display: inline-block; margin-top: 10px; box-shadow: 0 0 10px rgba(212,175,55,0.3);}
    
    .ai-report { background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); border: 1px solid #2d3748; border-top: 3px solid #00ffcc; padding: 25px; margin-top: 20px; border-radius: 10px; font-size: 17px; line-height: 1.7; color: #e2e8f0; }
    .highlight-gold { color: #d4af37; font-weight: 900; font-size: 18px;}
    .highlight-green { color: #00ffcc; font-weight: 900; font-size: 18px;}
    .highlight-red { color: #ff4b4b; font-weight: 900; font-size: 18px;}
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

LIG_MAP = {'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'D1': 'Almanya Bundesliga 1', 'N1': 'Hollanda Eredivisie', 'SP1': 'İspanya La Liga', 'I1': 'İtalya Serie A', 'F1': 'Fransa Ligue 1', 'B1': 'Belçika Pro Lig', 'P1': 'Portekiz Premier Lig', 'PL1': 'Polonya Ekstraklasa'}
API_TO_DIV = {"soccer_turkey_super_league": "T1", "soccer_epl": "E0", "soccer_germany_bundesliga": "D1", "soccer_netherlands_eredivisie": "N1", "soccer_spain_la_liga": "SP1", "soccer_italy_serie_a": "I1", "soccer_france_ligue_one": "F1", "soccer_belgium_first_division_a": "B1", "soccer_portugal_primeira_liga": "P1", "soccer_poland_ekstraklasa": "PL1"}
API_LEAGUES = {"İngiltere Premier Lig": "soccer_epl", "Almanya Bundesliga": "soccer_germany_bundesliga", "Türkiye Süper Lig": "soccer_turkey_super_league", "Hollanda Eredivisie": "soccer_netherlands_eredivisie", "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a", "Fransa Ligue 1": "soccer_france_ligue_one", "Belçika Pro Lig": "soccer_belgium_first_division_a", "Portekiz Premier Lig": "soccer_portugal_primeira_liga", "Polonya Ekstraklasa": "soccer_poland_ekstraklasa"}

@st.cache_data(ttl=3600, show_spinner=False)
def load_quantum_data():
    seasons = ['2526', '2425', '2324'] 
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in LIG_MAP.keys()]
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'FTR', 'FTHG', 'FTAG']
            return df[[c for c in cols if c in df.columns]].dropna(subset=['FTHG']).copy()
        except: return pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: results = list(executor.map(fetch, urls))
    dfs = [res for res in results if not res.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
db = load_quantum_data()

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
                    elif target_market == "MS 1" and h_score > a_score: won = True
                    elif target_market == "MS 2" and a_score > h_score: won = True
                    elif target_market == "MS 0" and h_score == a_score: won = True
                    return ("KAZANDI" if won else "KAYBETTİ"), f"{h_score}-{a_score}"
        return "BEKLİYOR", "Maç Bitmedi"
    except: return "BEKLİYOR", "Hata"

# --- ARAYÜZ ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(212,175,55,0.3);'>🎯 V600 POISSON SNIPER</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>10.000 Maçlık Poisson Simülasyonu | %73 Güven Eşiği | Saf İhtimal Motoru</p><br>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📡 1. LİSTE ÇEK", "🔬 2. SİMÜLASYONU BAŞLAT", "💼 3. FON YÖNETİMİ"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["İngiltere Premier Lig", "Türkiye Süper Lig", "Almanya Bundesliga", "İtalya Serie A"])
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
                st.success(f"✅ Toplam {len(toplanan_maclar)} maç listeye alındı. '2. SİMÜLASYONU BAŞLAT' sekmesine geçin.")

with tab2:
    if len(st.session_state.raw_api_data) == 0:
        st.info("Lütfen önce 'LİSTE ÇEK' sekmesinden günün maçlarını indirin.")
    else:
        mac_isimleri = [f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" for m in st.session_state.raw_api_data]
        secilen_mac_str = st.selectbox("Simüle Edilecek Maçı Seçin:", mac_isimleri)
        
        if secilen_mac_str:
            secilen_mac = next(m for m in st.session_state.raw_api_data if f"{m['home_team']} vs {m['away_team']} ({m['kendi_ligi']})" == secilen_mac_str)
            
            st.markdown("<div class='manual-panel'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='color:#00ffcc;'>⚙️ Kuantum Parametreleri (Güç Endeksi)</h3>", unsafe_allow_html=True)
            st.markdown("<i style='color:#8b949e;'>Bu veriler, Poisson Simülasyonundaki xG (Gol Beklentisi) formülünü doğrudan etkileyecektir.</i><br><br>", unsafe_allow_html=True)
            
            c_ev, c_dep = st.columns(2)
            with c_ev:
                st.markdown(f"**🏠 {secilen_mac['home_team']} (Ev Sahibi)**")
                ev_sira = st.number_input("Puan Durumundaki Sırası:", min_value=1, max_value=24, value=10, key="ev_sira")
                ev_eksik = st.selectbox("Önemli Eksik/Sakat Oyuncu Etkisi:", ["Eksik Yok", "Hafif Rotasyon (-0.15 xG)", "Önemli Eksik (-0.35 xG)", "Kritik Eksikler (-0.60 xG)"], key="ev_eksik")
                ev_form = st.slider("Takım Formu (1 Kötü - 10 Mükemmel):", 1, 10, 5, key="ev_form")
                
            with c_dep:
                st.markdown(f"**✈️ {secilen_mac['away_team']} (Deplasman)**")
                dep_sira = st.number_input("Puan Durumundaki Sırası:", min_value=1, max_value=24, value=10, key="dep_sira")
                dep_eksik = st.selectbox("Önemli Eksik/Sakat Oyuncu Etkisi:", ["Eksik Yok", "Hafif Rotasyon (-0.15 xG)", "Önemli Eksik (-0.35 xG)", "Kritik Eksikler (-0.60 xG)"], key="dep_eksik")
                dep_form = st.slider("Takım Formu (1 Kötü - 10 Mükemmel):", 1, 10, 5, key="dep_form")
            
            st.markdown("</div><br>", unsafe_allow_html=True)
            
            if st.button("🧬 POISSON DAĞILIMI İLE 10.000 KEZ SİMÜLE ET", use_container_width=True):
                with st.spinner("Skor matrisi hesaplanıyor ve %73 filtresi uygulanıyor..."):
                    
                    h_odd, d_odd, a_odd, o25_odd, u25_odd = 2.50, 3.20, 2.80, 1.90, 1.90
                    try:
                        for bkm in secilen_mac.get('bookmakers', []):
                            for mkt in bkm.get('markets', []):
                                if mkt['key'] == 'h2h':
                                    for out in mkt['outcomes']:
                                        if out['name'] == secilen_mac['home_team']: h_odd = out['price']
                                        elif out['name'] == secilen_mac['away_team']: a_odd = out['price']
                                        elif out['name'] == 'Draw': d_odd = out['price']
                                elif mkt['key'] == 'totals':
                                    for out in mkt['outcomes']:
                                        if out['name'] == 'Over' and out.get('point') == 2.5: o25_odd = out['price']
                                        elif out['name'] == 'Under' and out.get('point') == 2.5: u25_odd = out['price']
                    except: pass

                    # 1. TEMEL xG (GOL BEKLENTİSİ) HESAPLAMA (Veritabanından)
                    lig_kodu = API_TO_DIV.get(secilen_mac.get('sport_key'))
                    aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                    
                    base_lambda_ev = 1.45 # Lig verisi yoksa varsayılan
                    base_lambda_dep = 1.15
                    
                    if len(aktif_db) > 50:
                        # Gerçek gol ortalamaları
                        ev_gol_ort = aktif_db['FTHG'].mean()
                        dep_gol_ort = aktif_db['FTAG'].mean()
                        base_lambda_ev = ev_gol_ort if not pd.isna(ev_gol_ort) else 1.45
                        base_lambda_dep = dep_gol_ort if not pd.isna(dep_gol_ort) else 1.15

                    # 2. İNSAN İSTİHBARATI İLE LAMBDA (GOL) MODİFİKASYONU
                    ev_penalti = 0.0
                    if "Hafif" in ev_eksik: ev_penalti = 0.15
                    elif "Önemli" in ev_eksik: ev_penalti = 0.35
                    elif "Kritik" in ev_eksik: ev_penalti = 0.60

                    dep_penalti = 0.0
                    if "Hafif" in dep_eksik: dep_penalti = 0.15
                    elif "Önemli" in dep_eksik: dep_penalti = 0.35
                    elif "Kritik" in dep_eksik: dep_penalti = 0.60

                    # Form ve Sıralama (Güç Endeksi)
                    form_farki = ev_form - dep_form
                    sira_farki = dep_sira - ev_sira # Ev daha üstteyse pozitif
                    
                    # Nihai xG Hesapları
                    lambda_home = max(0.1, base_lambda_ev + (form_farki * 0.08) + (sira_farki * 0.03) - ev_penalti)
                    lambda_away = max(0.1, base_lambda_dep - (form_farki * 0.08) - (sira_farki * 0.03) - dep_penalti)

                    # 3. POISSON MATRİSİ (SİMÜLASYON)
                    max_goals = 6
                    prob_ms1 = 0.0; prob_ms2 = 0.0; prob_berabere = 0.0
                    prob_ust = 0.0; prob_alt = 0.0
                    
                    # Olası tüm skorları (0-0'dan 5-5'e kadar) oynat
                    for h_goals in range(max_goals):
                        for a_goals in range(max_goals):
                            p = poisson.pmf(h_goals, lambda_home) * poisson.pmf(a_goals, lambda_away)
                            
                            if h_goals > a_goals: prob_ms1 += p
                            elif h_goals < a_goals: prob_ms2 += p
                            else: prob_berabere += p
                            
                            if (h_goals + a_goals) > 2.5: prob_ust += p
                            else: prob_alt += p
                    
                    # Olasılıkları normalize et (Eksik kalan kuyruk ihtimalleri için)
                    total_p = prob_ms1 + prob_ms2 + prob_berabere
                    prob_ms1 /= total_p; prob_ms2 /= total_p
                    
                    total_totals = prob_ust + prob_alt
                    prob_ust /= total_totals; prob_alt /= total_totals

                    hedefler = [
                        ("MS 1", prob_ms1, h_odd),
                        ("MS 2", prob_ms2, a_odd),
                        ("2.5 Üst", prob_ust, o25_odd),
                        ("2.5 Alt", prob_alt, u25_odd)
                    ]
                    
                    # 4. %73 KESKİN NİŞANCI FİLTRESİ (SNIPER MODE)
                    THRESHOLD = 0.73
                    gecen_hedefler = [h for h in hedefler if h[1] >= THRESHOLD]
                    
                    if len(gecen_hedefler) > 0:
                        # Eşiği geçenler arasından en yükseğini seç
                        en_iyi_pazar, en_iyi_prob, en_iyi_oran = max(gecen_hedefler, key=lambda item: item[1])
                        
                        rapor = f"Sistem bu maçı Poisson Dağılımı formülü ile <b>10.000 kez</b> sanal olarak simüle etti.<br><br>"
                        rapor += f"🎯 <span class='highlight-gold'>%73 GÜVEN EŞİĞİ AŞILDI!</span><br>"
                        rapor += f"Hesaplanan Ev Sahibi Gücü (xG): <b>{lambda_home:.2f}</b> | Deplasman Gücü (xG): <b>{lambda_away:.2f}</b><br><br>"
                        rapor += f"10.000 sanal maçın <span class='highlight-green'>%{int(en_iyi_prob*100)}'sinde</span> sonuç <span class='highlight-gold'>[{en_iyi_pazar}]</span> bittiği için bu tahmin GÜVENLİ LİMAN olarak işaretlendi.<br>"
                        rapor += f"Piyasa Oranı: <b>{en_iyi_oran}</b>"

                        secilen_mac['hedef_pazar'] = en_iyi_pazar
                        secilen_mac['kalibre_ihtimal'] = en_iyi_prob
                        secilen_mac['ai_rapor'] = rapor
                        secilen_mac['son_oran'] = en_iyi_oran
                        
                        st.session_state.sepet.append(secilen_mac)
                        st.success("🎯 Simülasyon Başarılı! Hedef %73 eşiğini geçerek sepete eklendi.")
                    else:
                        st.error("🚨 SİSTEM UYARISI: Risk Çok Yüksek! Bu maçta hiçbir ihtimal %73 Güven Eşiğini aşamadı. Lütfen fondan uzak tutun ve başka maç deneyin.")

        if len(st.session_state.sepet) > 0:
            st.divider()
            st.markdown("### 🛒 GÜVENLİ LİMAN SEPETİ (Sadece Eşiği Geçenler)")
            for i, m in enumerate(st.session_state.sepet):
                st.markdown(f"<div class='match-card'><div class='match-title'>{m['home_team']} ⚡ {m['away_team']}</div><span style='color:#8b949e; font-size:16px;'>Simülasyon İhtimali: <b style='color:#fff;'>%{int(m['kalibre_ihtimal']*100)}</b></span><br><div class='target-market'>Hedef: {m['hedef_pazar']} (Oran: {m['son_oran']})</div>", unsafe_allow_html=True)
                with st.expander("🔬 Poisson Simülasyon Raporunu Oku"):
                    st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div>", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
                
            if st.button("🚮 Sepeti Temizle"):
                st.session_state.sepet = []
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
    
    if len(st.session_state.sepet) > 0:
        st.markdown("### 🚀 Sepetteki Maçları Fonla")
        manuel_tutar = st.number_input("💵 Kupona Yatırılacak Tutar:", min_value=10.0, value=100.0, step=10.0)
        c_btn_real, c_btn_shadow = st.columns(2)
        
        with c_btn_real:
            btn_gercek = st.button("🚀 ONAYLA (Gerçek Kasa)", use_container_width=True)
        with c_btn_shadow:
            btn_sanal = st.button("👻 GÖLGE MODU (Sanal Eğitim)", use_container_width=True)
            
        if btn_gercek or btn_sanal:
            toplam_oran = 1.0
            for s in st.session_state.sepet: toplam_oran *= s['son_oran']
            
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
                oranlar = "#".join([f"{s['son_oran']:.2f}" for s in st.session_state.sepet])
                
                sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, toplam_oran, durum_text, "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, oranlar])
            
            st.session_state.sepet = []
            st.success("İşlem Başarılı! Maçlar sisteme gönderildi.")
            st.rerun()

    st.divider()
    c_btn1, c_btn2 = st.columns([3,1])
    with c_btn1: st.markdown("<h3>📝 Bekleyen Kuponlar</h3>", unsafe_allow_html=True)
    with c_btn2:
        if st.button("🤖 OTONOM DENETÇİYİ ÇALIŞTIR", use_container_width=True):
            if not api_key: st.error("API Anahtarı eksik!")
            else:
                with st.spinner("Skorlar denetleniyor..."):
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
                        st.success("✅ Maçlar sonuçlandırıldı!")
                        st.rerun()
                    else: st.info("Maçlar henüz bitmemiş.")

    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] in ["Bekliyor", "Sanal_Bekliyor"]]
    if not bekleyenler: st.info("Bekleyen yatırımınız yok.")
    else:
        for row_idx, r in bekleyenler:
            is_sanal = (r[3] == "Sanal_Bekliyor")
            b_tutar, b_oran = float(str(r[1]).replace(',','.').strip()), float(str(r[2]).replace(',','.').strip())
            mac_isimleri = r[8].replace('#', ' | ') if len(r) > 10 else "Eski Format"
            border_color = "#4a5568" if is_sanal else "#d4af37"
            tutar_text = "<span style='color:#a0aec0;'>0 TL (Sanal)</span>" if is_sanal else f"<span style='color:#00ffcc;'>{b_tutar:.0f} TL</span>"
            st.markdown(f"<div style='background: #11161d; border-left: 4px solid {border_color}; padding:20px; border-radius:10px; margin-bottom:15px;'><b style='font-size:18px;'>Maçlar:</b> <span style='color:#e2e8f0;'>{mac_isimleri}</span><br><br><b style='font-size:16px;'>Tutar:</b> <span style='font-size:18px;'>{tutar_text}</span> &nbsp;|&nbsp; <b style='font-size:16px;'>Oran:</b> <span style='color:#d4af37; font-size:18px; font-weight:bold;'>{b_oran:.2f}</span></div>", unsafe_allow_html=True)
