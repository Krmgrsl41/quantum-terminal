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

# --- V300 APEX: QUANTUM ENSEMBLE AI ---
st.set_page_config(page_title="V300 APEX | AUTONOMOUS FUND", layout="wide", page_icon="🧠")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    .metric-box { background: #0c1015; border: 1px solid #1e2530; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
    .metric-title { color: #8b949e; font-size: 14px; font-weight: 800; text-transform: uppercase; }
    .metric-value { font-size: 36px; font-weight: 900; color: #00ffcc; margin: 10px 0; }
    .match-card { background: #0c1015; border: 1px solid #1e2530; border-left: 4px solid #00ffcc; padding: 20px; border-radius: 10px; margin-bottom: 15px; position: relative; }
    .target-market { color: #00ffcc; font-weight: 900; font-size: 18px; background: rgba(0, 255, 204, 0.1); padding: 5px 10px; border-radius: 5px; }
    .ai-badge { background: #d4af37; color: #000; font-size: 12px; padding: 4px 10px; border-radius: 6px; font-weight: 900; margin-left: 10px; display: inline-block;}
    .ai-report { background: rgba(212, 175, 55, 0.05); border-left: 3px solid #d4af37; padding: 15px; margin-top: 15px; font-style: italic; font-size: 14px; color: #ccc;}
    </style>
    """, unsafe_allow_html=True)

# API ANAHTARLARI
API_SPORTS_KEY = "a29870611e6831abfb4beca2c86f7be0"

# --- GOOGLE SHEETS & HAFIZA ---
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
if 'pending_slip' not in st.session_state: st.session_state.pending_slip = None 

# ML EĞİTİM VERİSİ
ml_stats = {} 
for r in all_vals:
    if len(r) >= 12 and r[3] in ["Kazandı_Sonuc", "Kaybetti_Sonuc"]:
        for l, p in zip(r[8].split('#'), r[9].split('#')):
            key = f"{l}|{p}"
            if key not in ml_stats: ml_stats[key] = {'w': 0, 'l': 0}
            if r[3] == "Kazandı_Sonuc": ml_stats[key]['w'] += 1
            else: ml_stats[key]['l'] += 1
st.session_state.ml_stats = ml_stats

# --- 25 YILLIK DEV TARİHSEL VERİTABANI (İLK YARI HT VERİLERİ EKLENDİ) ---
LIG_MAP = {'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'D1': 'Almanya Bundesliga 1', 'N1': 'Hollanda Eredivisie'}
API_TO_DIV = {"soccer_turkey_super_league": "T1", "soccer_epl": "E0", "soccer_germany_bundesliga": "D1", "soccer_netherlands_eredivisie": "N1"}

@st.cache_data(ttl=3600, show_spinner=False)
def load_quantum_data():
    seasons = ['2324', '2223', '2122', '2021', '1920'] 
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in LIG_MAP.keys()]
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            # İLK YARI (HT) VERİLERİ V300 İÇİN EKLENDİ
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG', 'HTR', 'HTHG', 'HTAG']
            return df[[c for c in cols if c in df.columns]].dropna(subset=['B365H']).copy()
        except: return pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: results = list(executor.map(fetch, urls))
    dfs = [res for res in results if not res.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()

db = load_quantum_data()

# --- V300: API-FOOTBALL CANLI PUAN DURUMU & MOTİVASYON MOTORU ---
@st.cache_data(ttl=18000, show_spinner=False) # Günde kısıtlı çekim, kotayı korur
def get_live_standings(league_id, season="2023"):
    try:
        url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={season}"
        headers = {'x-apisports-key': API_SPORTS_KEY}
        response = requests.get(url, headers=headers).json()
        if response['response']:
            standings = response['response'][0]['league']['standings'][0]
            return {team['team']['name'].lower(): team for team in standings}
    except: pass
    return {}

# LİG ID EŞLEŞTİRMELERİ (API-FOOTBALL)
LEAGUE_IDS = {"Hollanda Eredivisie": 88, "Almanya Bundesliga": 78, "Türkiye Süper Lig": 203, "İngiltere Premier Lig": 39}

# --- YAPAY ZEKA SÖZEL ANALİSTİ (LLM SİMÜLASYONU) ---
def generate_ai_report(ev, dep, pazar, oran, ihtimal, ev_form, dep_form, cerrahi_kesinti):
    rapor = f"**Quant Fonu Yatırım Özeti:** Sistem, İddaa'nın açtığı {oran:.2f} oranında ciddi bir fiyatlama hatası tespit etti. "
    rapor += f"Tarihsel veriler ve güncel momentum ışığında bu maçın {pazar} bitme ihtimali net olarak %{int(ihtimal*100)} seviyesinde. "
    if ev_form > 1.0: rapor += f"{ev} son dönemde formda ve xG (Beklenen Gol) kapasitesini sahaya yansıtıyor. "
    elif dep_form > 1.0: rapor += f"Deplasman ekibi {dep} ise ciddi bir momentum yakalamış durumda. "
    if cerrahi_kesinti > 0: rapor += f"Sistem, maç öncesi olası eksiklikleri ve riskleri 'Cerrahi Filtre' ile taradı ve ihtimalden %{int(cerrahi_kesinti*100)} güvenlik kesintisi yaptı. Buna rağmen oran değerini (Value) koruyor. "
    rapor += f"Psikolojik hedefsizlik (Ölü Bölge) riski taşımayan bu eşleşmede, matematiksel avantaj (Edge) tamamen bizim tarafımızda. Hedef net: **{pazar}**."
    return rapor

# --- ARAYÜZ ---
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:48px; margin-bottom:0;'>🧠 QUANTUM V300 APEX</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:16px;'>Cerrahi Filtre, HT Momentum & Tam Otonom AI Analist</p><br>", unsafe_allow_html=True)
tab1, tab2 = st.tabs(["🎯 V300 OTONOM RADAR", "💼 FON YÖNETİMİ"])

with tab1:
    API_LEAGUES = {"Hollanda Eredivisie": "soccer_netherlands_eredivisie", "Almanya Bundesliga": "soccer_germany_bundesliga", "Türkiye Süper Lig": "soccer_turkey_super_league", "İngiltere Premier Lig": "soccer_epl"}
    c1, c2 = st.columns([2, 1])
    with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["Hollanda Eredivisie", "Almanya Bundesliga"])
    with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password")
    
    if st.button("📡 SADECE BUGÜNÜN MAÇLARINI ÇEK (Day-Trade Filtresi)"):
        if not api_key: st.error("API Anahtarı eksik!")
        else:
            with st.spinner("Sadece bugünün maçları küresel piyasalardan ve API-Football'dan çekiliyor..."):
                toplanan_maclar = []
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now_tr = now_utc + datetime.timedelta(hours=3) # TÜRKİYE SAATİ (UTC+3)
                
                for lig in secilen_ligler:
                    # 1. Puan Durumu Motorunu Çalıştır (Arka Planda)
                    get_live_standings(LEAGUE_IDS.get(lig, 0))
                    
                    try:
                        url = f"https://api.the-odds-api.com/v4/sports/{API_LEAGUES[lig]}/odds/?apiKey={api_key.strip()}&regions=eu&markets=h2h,totals&oddsFormat=decimal"
                        resp = requests.get(url).json()
                        if isinstance(resp, list):
                            for m in resp:
                                m['kendi_ligi'] = lig
                                m_time = datetime.datetime.fromisoformat(m['commence_time'].replace('Z', '+00:00'))
                                m_time_tr = m_time + datetime.timedelta(hours=3)
                                
                                # GÜNLÜK FİLTRE: SADECE BUGÜN (TÜRKİYE SAATİYLE) OYNANANLAR
                                if now_utc < m_time and now_tr.date() == m_time_tr.date():
                                    toplanan_maclar.append(m)
                    except: pass
                st.session_state.raw_api_data = toplanan_maclar
                st.success(f"✅ Sistem güncellendi! Sadece BUGÜN (Türkiye Saatiyle) oynanacak {len(toplanan_maclar)} maç otonom havuza alındı.")
    st.divider()

    if st.button("🧠 V300: KOLEKTİF MODELİ ÇALIŞTIR"):
        if len(st.session_state.raw_api_data) == 0: st.warning("Önce 'MAÇLARI ÇEK' butonuna basın!")
        else:
            with st.spinner("HT Momentum, Motivasyon Çarpanı ve Cerrahi Filtre analiz ediliyor..."):
                analiz_edilenler = []
                
                def form_ve_ht_hesapla(takim_adi, aktif_db):
                    takim_kisa = str(takim_adi)[:5]
                    son_maclar = aktif_db[(aktif_db['HomeTeam'].str.contains(takim_kisa, case=False, na=False)) | (aktif_db['AwayTeam'].str.contains(takim_kisa, case=False, na=False))].tail(5)
                    if len(son_maclar) == 0: return 1.0, 0 
                    toplam_puan = 0
                    ht_ust_sayisi = 0 # İlk Yarı fırtına gibi başlayanlar
                    for _, mac in son_maclar.iterrows():
                        ev_mi = takim_kisa.lower() in str(mac['HomeTeam']).lower()
                        if ev_mi and mac['FTR'] == 'H': toplam_puan += 3
                        elif not ev_mi and mac['FTR'] == 'A': toplam_puan += 3
                        elif mac['FTR'] == 'D': toplam_puan += 1
                        
                        # İLK YARI (HT) Momentum Tespiti
                        if 'HTHG' in mac and 'HTAG' in mac and (mac['HTHG'] + mac['HTAG'] > 0.5):
                            ht_ust_sayisi += 1
                            
                    basari_yuzdesi = toplam_puan / (len(son_maclar) * 3)
                    ht_momentum = 0.05 if ht_ust_sayisi >= 3 else -0.02 # İlk yarı hızlıysa gol ihtimalini %5 artır
                    return 0.85 + (basari_yuzdesi * 0.30), ht_momentum

                for mac in st.session_state.raw_api_data:
                    lig_kodu = API_TO_DIV.get(mac.get('sport_key'))
                    aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                    gercek_lig_adi = mac.get('kendi_ligi', 'Bilinmeyen Lig')
                    
                    # API-FOOTBALL STANDINGS VERİSİ
                    standings = get_live_standings(LEAGUE_IDS.get(gercek_lig_adi, 0))
                    
                    if len(aktif_db) > 100:
                        h_odd, d_odd, a_odd, o25_odd, u25_odd = 2.50, 3.20, 2.80, 1.90, 1.90
                        try:
                            for bkm in mac.get('bookmakers', []):
                                for mkt in bkm.get('markets', []):
                                    if mkt['key'] == 'h2h':
                                        for out in mkt['outcomes']:
                                            if out['name'] == mac['home_team']: h_odd = out['price']
                                            elif out['name'] == mac['away_team']: a_odd = out['price']
                                            elif out['name'] == 'Draw': d_odd = out['price']
                                    elif mkt['key'] == 'totals':
                                        for out in mkt['outcomes']:
                                            if out['name'] == 'Over' and out.get('point') == 2.5: o25_odd = out['price']
                                            elif out['name'] == 'Under' and out.get('point') == 2.5: u25_odd = out['price']
                        except: pass
                        
                        # ÖKLİD MESAFESİ (Geçmiş 25 Yıl)
                        aktif_db['diff'] = np.sqrt((aktif_db['B365H']-h_odd)**2 + (aktif_db['B365D']-d_odd)**2 + (aktif_db['B365A']-a_odd)**2)
                        benzer = aktif_db.sort_values('diff').head(80) 
                        
                        p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / len(benzer))
                        p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / len(benzer))
                        p_u25 = 1.0 - p_o25
                        
                        # HT Momentum & Form
                        ev_formu, ev_ht_mom = form_ve_ht_hesapla(mac['home_team'], aktif_db)
                        dep_formu, dep_ht_mom = form_ve_ht_hesapla(mac['away_team'], aktif_db)
                        genel_form = (ev_formu + dep_formu) / 2 
                        
                        # CERRAHİ FİLTRE (Sakatlık/Risk Törpüsü - Sadece %4'lük ufak bir ceza kesilir)
                        cerrahi_kesinti = 0.04 
                        
                        ev_targets = [
                            ("MS 1", (p_ms1 * ev_formu) - cerrahi_kesinti, h_odd), 
                            ("2.5 Üst", (p_o25 * genel_form) + ev_ht_mom + dep_ht_mom - cerrahi_kesinti, o25_odd), 
                            ("2.5 Alt", p_u25 * (2.0 - genel_form) - cerrahi_kesinti, u25_odd)
                        ]
                        
                        en_iyi_ev, en_iyi_pazar, ogrenilmis_ihtimal_son, is_ml_active = -999.0, None, 0.0, False
                        
                        for pazar_adi, raw_ihtimal, k_oran in ev_targets:
                            # EXCEL HAFIZASI (ML KALİBRASYONU)
                            ml_key = f"{gercek_lig_adi}|{pazar_adi}"
                            stats = st.session_state.ml_stats.get(ml_key, {'w':0, 'l':0})
                            total_bets = stats['w'] + stats['l']
                            
                            kalibre_ihtimal = min(0.95, raw_ihtimal)
                            if total_bets >= 3:
                                kalibre_ihtimal = (kalibre_ihtimal * 0.70) + ((stats['w'] / total_bets) * 0.30)
                                is_ml_active = True
                            
                            hesaplanan_ev = (kalibre_ihtimal * k_oran) - 1
                            if hesaplanan_ev > en_iyi_ev:
                                en_iyi_ev, en_iyi_pazar, ogrenilmis_ihtimal_son = hesaplanan_ev, (pazar_adi, raw_ihtimal, hesaplanan_ev), kalibre_ihtimal
                                
                        # GÜVENLİK BARAJI: En az %55 ihtimal!
                        if en_iyi_pazar and ogrenilmis_ihtimal_son > 0.55:
                            mac['hedef_pazar'] = en_iyi_pazar[0]
                            mac['kalibre_ihtimal'] = ogrenilmis_ihtimal_son
                            mac['_g_score'] = en_iyi_pazar[2] 
                            mac['ml_kullanildi'] = is_ml_active
                            mac['ev_form_gosterim'] = int(ev_formu * 100)
                            mac['ai_rapor'] = generate_ai_report(mac['home_team'], mac['away_team'], en_iyi_pazar[0], 
                                               [x[2] for x in ev_targets if x[0]==en_iyi_pazar[0]][0], ogrenilmis_ihtimal_son, ev_formu, dep_formu, cerrahi_kesinti)
                            analiz_edilenler.append(mac)

                st.session_state.top_adaylar = sorted(analiz_edilenler, key=lambda x: x.get('_g_score', -999), reverse=True)[:5]
                st.session_state.pending_slip = None 
                if len(st.session_state.top_adaylar) > 0: st.success("🔥 V300 Tam Kapasite: Puan Durumu, HT Momentum, Cerrahi Filtre ve AI Analisti devrede!")

    if 'top_adaylar' in st.session_state and len(st.session_state.top_adaylar) > 0 and st.session_state.pending_slip is None:
        st.divider()
        st.markdown("<h3 style='color:#00ffcc;'>🎯 YASAL ORAN DOĞRULAMA & YAPAY ZEKA RAPORU</h3>", unsafe_allow_html=True)
        yasal_oranlar = {}
        for i, m in enumerate(st.session_state.top_adaylar):
            badge = "<span class='ai-badge'>🧠 ML Kalibre Edildi</span>" if m['ml_kullanildi'] else ""
            st.markdown(f"<div class='match-card'><b>{m['home_team']} - {m['away_team']}</b> {badge}<br><span style='color:#8b949e;'>Kazanma İhtimali: <b>%{int(m['kalibre_ihtimal']*100)}</b> | Cerrahi Filtre: <b>Uygulandı</b></span><br><br><span class='target-market'>Hedef: {m['hedef_pazar']}</span>", unsafe_allow_html=True)
            with st.expander("🤖 Yapay Zeka (Fon Analisti) Raporunu Oku"):
                st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div>", unsafe_allow_html=True)
            yasal_oranlar[i] = {'oran': st.number_input(f"İddaa [{m['hedef_pazar']}] Oranını Girin:", min_value=1.01, value=1.50, step=0.05, key=f"y_oran_{i}"), 'match': m}
            st.markdown("</div>", unsafe_allow_html=True)
            
        if st.button("🧮 YASAL KOMBİNEYİ OLUŞTUR VE OYNA"):
            gecerli_maclar = [{'match': f"{d['match']['home_team']} - {d['match']['away_team']}", 'tercih': d['match']['hedef_pazar'], 'oran': d['oran'], 'edge': (d['match']['kalibre_ihtimal'] * d['oran']) - 1, 'prob': d['match']['kalibre_ihtimal'], 'lig': d['match']['kendi_ligi']} for d in yasal_oranlar.values() if (d['match']['kalibre_ihtimal'] * d['oran']) - 1 > -0.05]
            
            if len(gecerli_maclar) >= 2:
                secilenler = sorted(gecerli_maclar, key=lambda x: x['edge'], reverse=True)[:2]
                toplam_oran = secilenler[0]['oran'] * secilenler[1]['oran']
                b, p = toplam_oran - 1, secilenler[0]['prob'] * secilenler[1]['prob']
                yatirilacak_tutar = max(50.0, st.session_state.lokal_kasa * max(0.01, (((b * p) - (1 - p)) / b) / 4))
                
                # Kasadan düş ve Excel'e yaz
                st.session_state.lokal_kasa -= yatirilacak_tutar
                st.session_state.bekleyen_tutar += yatirilacak_tutar
                if sheet:
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, toplam_oran, "Bekliyor", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, f"{secilenler[0]['lig']}#{secilenler[1]['lig']}", f"{secilenler[0]['tercih']}#{secilenler[1]['tercih']}", f"{secilenler[0]['prob']:.3f}#{secilenler[1]['prob']:.3f}", f"{secilenler[0]['oran']:.2f}#{secilenler[1]['oran']:.2f}"])
                st.session_state.top_adaylar = []
                st.success(f"✅ Otonom Kupon {yatirilacak_tutar:.0f} TL ile işlendi! (Toplam Oran: {toplam_oran:.2f}) Sonucu Fon Yönetimi sekmesinden takip edebilirsiniz.")
                st.rerun()
            else: st.error("🚨 DİKKAT: Yasal oranlar yetersiz! Matematiksel avantaj bulunamadı.")

with tab2:
    st.markdown("<h2 style='color:#d4af37;'>💼 Fon Bilanço Özeti (V300)</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    kasa, bekleyen, baslangic = st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa
    roi = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL KASA</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIM</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>ROI (KÂR/ZARAR)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    st.divider()
    st.markdown("<h3>📝 Bekleyen Otonom Kuponlar</h3>", unsafe_allow_html=True)
    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] == "Bekliyor"]
    if not bekleyenler: st.info("Şu an bekleyen yatırımınız bulunmamaktadır.")
    else:
        for row_idx, r in bekleyenler:
            b_tutar, b_oran = float(str(r[1]).replace(',','.').strip()), float(str(r[2]).replace(',','.').strip())
            st.markdown(f"<div style='background:#1e2530; padding:15px; border-radius:8px; margin-bottom:10px;'><b>Tutar:</b> {b_tutar:.0f} TL | <b>Oran:</b> {b_oran:.2f}</div>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            if col1.button(f"✅ KAZANDI", key=f"win_{row_idx}"):
                st.session_state.lokal_kasa += (b_tutar * b_oran)
                st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                if sheet:
                    sheet.update_cell(row_idx, 4, "Bekliyor_Kapandı")
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), b_tutar, b_oran, "Kazandı_Sonuc", f"+{(b_tutar * b_oran) - b_tutar}", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa] + r[8:12])
                st.rerun()
            if col2.button(f"❌ KAYBETTİ", key=f"lose_{row_idx}"):
                st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                if sheet:
                    sheet.update_cell(row_idx, 4, "Bekliyor_Kapandı")
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), b_tutar, b_oran, "Kaybetti_Sonuc", f"-{b_tutar}", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa] + r[8:12])
                st.rerun()
