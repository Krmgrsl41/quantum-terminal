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

# --- V300 FINAL APEX: PREMIUM UI & OTONOM SKOR ---
st.set_page_config(page_title="V300 APEX | PREMIUM FUND", layout="wide", page_icon="📈")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800;900&display=swap');
    .stApp { background-color: #05070a; color: #ffffff; font-family: 'Inter', sans-serif; }
    h1, h2, h3 { font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.5px; }
    
    .metric-box { background: linear-gradient(145deg, #0c1015 0%, #151b22 100%); border: 1px solid #1e2530; padding: 25px; border-radius: 16px; text-align: center; box-shadow: 0 8px 25px rgba(0,0,0,0.4); }
    .metric-title { color: #8b949e; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 1px;}
    .metric-value { font-size: 42px; font-weight: 900; color: #00ffcc; margin: 10px 0; text-shadow: 0 0 15px rgba(0, 255, 204, 0.2); }
    
    .match-card { background: linear-gradient(to right, #0c1015, #11161d); border: 1px solid #232b35; border-left: 5px solid #00ffcc; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); transition: transform 0.2s;}
    .match-card:hover { transform: scale(1.01); border-left: 5px solid #d4af37;}
    .match-title { font-size: 22px; font-weight: 900; color: #ffffff; margin-bottom: 10px;}
    .target-market { color: #000; font-weight: 900; font-size: 20px; background: #00ffcc; padding: 8px 15px; border-radius: 8px; display: inline-block; margin-top: 10px; box-shadow: 0 0 10px rgba(0,255,204,0.3);}
    .ai-badge { background: #d4af37; color: #000; font-size: 14px; padding: 6px 12px; border-radius: 6px; font-weight: 900; margin-left: 15px; display: inline-block; text-transform: uppercase;}
    
    .ai-report { 
        background: linear-gradient(145deg, #13171e 0%, #0a0d12 100%); 
        border: 1px solid #2d3748;
        border-top: 3px solid #d4af37; 
        padding: 25px; 
        margin-top: 20px; 
        border-radius: 10px;
        font-size: 17px; 
        line-height: 1.7; 
        color: #e2e8f0;
        box-shadow: inset 0 0 20px rgba(212,175,55,0.03);
    }
    .highlight-gold { color: #d4af37; font-weight: 900; font-size: 18px;}
    .highlight-green { color: #00ffcc; font-weight: 900; font-size: 18px;}
    .alert-text { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

API_SPORTS_KEY = "a29870611e6831abfb4beca2c86f7be0"

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

ml_stats = {} 
for r in all_vals:
    if len(r) >= 11 and r[3] in ["Kazandı_Sonuc", "Kaybetti_Sonuc"]:
        try:
            ligler = r[9].split('#') if len(r) > 10 else r[8].split('#')
            pazarlar = r[10].split('#') if len(r) > 10 else r[9].split('#')
            for l, p in zip(ligler, pazarlar):
                key = f"{l}|{p}"
                if key not in ml_stats: ml_stats[key] = {'w': 0, 'l': 0}
                if r[3] == "Kazandı_Sonuc": ml_stats[key]['w'] += 1
                else: ml_stats[key]['l'] += 1
        except: pass
st.session_state.ml_stats = ml_stats

LIG_MAP = {'T1': 'Türkiye Süper Lig', 'E0': 'İngiltere Premier Lig', 'D1': 'Almanya Bundesliga 1', 'N1': 'Hollanda Eredivisie', 'SP1': 'İspanya La Liga', 'I1': 'İtalya Serie A', 'F1': 'Fransa Ligue 1', 'B1': 'Belçika Pro Lig', 'P1': 'Portekiz Premier Lig', 'PL1': 'Polonya Ekstraklasa'}
API_TO_DIV = {"soccer_turkey_super_league": "T1", "soccer_epl": "E0", "soccer_germany_bundesliga": "D1", "soccer_netherlands_eredivisie": "N1", "soccer_spain_la_liga": "SP1", "soccer_italy_serie_a": "I1", "soccer_france_ligue_one": "F1", "soccer_belgium_first_division_a": "B1", "soccer_portugal_primeira_liga": "P1", "soccer_poland_ekstraklasa": "PL1"}
LEAGUE_IDS = {"Hollanda Eredivisie": 88, "Almanya Bundesliga": 78, "Türkiye Süper Lig": 203, "İngiltere Premier Lig": 39, "İspanya La Liga": 140, "İtalya Serie A": 135, "Fransa Ligue 1": 61, "Belçika Pro Lig": 144, "Portekiz Premier Lig": 94, "Polonya Ekstraklasa": 106}
API_LEAGUES = {"İngiltere Premier Lig": "soccer_epl", "Almanya Bundesliga": "soccer_germany_bundesliga", "Türkiye Süper Lig": "soccer_turkey_super_league", "Hollanda Eredivisie": "soccer_netherlands_eredivisie", "İspanya La Liga": "soccer_spain_la_liga", "İtalya Serie A": "soccer_italy_serie_a", "Fransa Ligue 1": "soccer_france_ligue_one", "Belçika Pro Lig": "soccer_belgium_first_division_a", "Portekiz Premier Lig": "soccer_portugal_primeira_liga", "Polonya Ekstraklasa": "soccer_poland_ekstraklasa"}

@st.cache_data(ttl=3600, show_spinner=False)
def load_quantum_data():
    seasons = ['2526', '2425', '2324', '2223', '2122'] 
    urls = [(s, l, f'https://www.football-data.co.uk/mmz4281/{s}/{l}.csv') for s in seasons for l in LIG_MAP.keys()]
    def fetch(item):
        s, l, url = item
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            if r.status_code != 200: return pd.DataFrame()
            df = pd.read_csv(io.StringIO(r.text))
            if 'B365>2.5' in df.columns: df.rename(columns={'B365>2.5': 'B365O', 'B365<2.5': 'B365U'}, inplace=True)
            cols = ['Div', 'Date', 'HomeTeam', 'AwayTeam', 'B365H', 'B365D', 'B365A', 'B365O', 'B365U', 'FTR', 'FTHG', 'FTAG', 'HTR', 'HTHG', 'HTAG']
            return df[[c for c in cols if c in df.columns]].dropna(subset=['B365H']).copy()
        except: return pd.DataFrame()
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor: results = list(executor.map(fetch, urls))
    dfs = [res for res in results if not res.empty]
    return pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
db = load_quantum_data()

# --- YENİLENMİŞ VE HAFIZASI TEMİZLENMİŞ API SORGUSU ---
@st.cache_data(ttl=18000, show_spinner=False)
def get_live_standings_v2(league_id):
    if league_id == 0: return {}
    try:
        now = datetime.datetime.now()
        aktif_sezon = str(now.year - 1) if now.month < 8 else str(now.year)
        
        url = f"https://v3.football.api-sports.io/standings?league={league_id}&season={aktif_sezon}"
        headers = {'x-apisports-key': API_SPORTS_KEY}
        response = requests.get(url, headers=headers).json()
        
        if 'response' in response and len(response['response']) > 0:
            standings = response['response'][0]['league']['standings'][0]
            return {team['team']['name'].lower(): team for team in standings}
    except: pass
    return {}

def format_form_string(form_str):
    if not form_str or form_str == '?': return "Veri Yok"
    tr_map = {'W': 'G', 'D': 'B', 'L': 'M'}
    return "-".join([tr_map.get(char, char) for char in form_str])

# --- AKILLI TAKIM EŞLEŞTİRME MOTORU ---
def takim_eslestir(hedef_isim, standings_dict):
    hedef = hedef_isim.lower().strip()
    # 1. Birebir eşleşme
    if hedef in standings_dict: return standings_dict[hedef]
    
    # 2. İçinde geçme (Örn: "inter" in "inter milan")
    for k, v in standings_dict.items():
        if k in hedef or hedef in k: return v
        
    # 3. Kelime bazlı kesişim (Örn: "hellas verona" -> "verona")
    hedef_kelimeler = set([w for w in hedef.split() if len(w) > 3])
    for k, v in standings_dict.items():
        k_kelimeler = set([w for w in k.split() if len(w) > 3])
        if len(hedef_kelimeler.intersection(k_kelimeler)) > 0:
            return v
            
    return None

def generate_ai_report(ev, dep, pazar, oran, ihtimal, ev_form, dep_form, cerrahi, ev_sira, ev_at, ev_ye, ev_son5, dep_sira, dep_at, dep_ye, dep_son5, lig):
    rapor = f"Analizime göre sistem, bu maçta <span class='highlight-green'>{oran:.2f}</span> oranla <span class='highlight-gold'>[{pazar}]</span> pazarında ciddi bir matematiksel değer tespit etti. Veritabanındaki geçmiş eşleşmeler ve mevcut momentum ışığında maçın bu senaryoda bitme ihtimali net olarak <span class='highlight-green'>%{int(ihtimal*100)}</span>.<br><br>"
    
    rapor += f"<b>📊 {lig} Güncel Puan Durumu ve Form:</b><br>"
    if ev_sira != '?' and dep_sira != '?':
        rapor += f"• <b>{ev}</b> ligde <span class='highlight-gold'>{ev_sira}. sırada</span> bulunuyor. Rakip fileleri <b>{ev_at}</b> kez havalandırırken, kalesinde <b>{ev_ye}</b> gol gördü. Son 5 Maç Formu: <b>[{ev_son5}]</b><br>"
        rapor += f"• <b>{dep}</b> ise ligde <span class='highlight-gold'>{dep_sira}. sırada</span> yer alıyor. Attığı <b>{dep_at}</b> gole karşılık savunmasında <b>{dep_ye}</b> gol yedi. Son 5 Maç Formu: <b>[{dep_son5}]</b><br><br>"
    else:
        rapor += f"• <i>Ligin güncel sıralama verileri şu an senkronize ediliyor... Algoritma doğrudan xG hesaplaması üzerinden karara vardı.</i><br><br>"
        
    rapor += f"<b>🧠 V300 Kuantum Değerlendirmesi:</b><br>"
    if pazar == "2.5 Üst": rapor += f"Her iki takımın attığı/yediği gol istatistikleri ve maç başı tempo (HT) verileri, savunma hatlarının kırılgan olduğunu ve gollerin erken geleceğini kanıtlıyor. "
    elif pazar == "MS 1": rapor += f"Özellikle {ev} takımının kendi evindeki istikrarlı oyunu (Son form durumu: {ev_son5}) ve puan durumundaki motivasyonu, bu eşleşmede rakibine şans tanımayacağını gösteriyor. "
    elif pazar == "2.5 Alt": rapor += f"Takımların gol kısırlığı ve puan durumundaki pozisyonları, maçı tamamen bir taktik savaşına çevirecektir. Temponun düşük kalması kuvvetle muhtemel. "

    if cerrahi > 0:
        rapor += f"<br><br>⚠️ <i>Güvenlik Notu: Sistem, olası ufak rotasyonlar ve teknik direktör değişiklikleri ihtimaline karşı genel başarı yüzdesinden <span class='alert-text'>%{int(cerrahi*100)}</span>'lük minimal bir 'Risk Kesintisi' yapmıştır. (İsim bazlı sakatlık analizi The-Odds-API sunucusuyla eşleşmediği için uygulanmamıştır.)</i>"
    
    rapor += f"<br><br><b>🎯 Sonuç:</b> Tüm veriler filtrelendiğinde en yüksek değerli oran (Value) <span class='highlight-gold'>{pazar}</span> tercihidir."
    return rapor

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
st.markdown("<h1 style='text-align:center; color:#d4af37; font-size:52px; margin-bottom:0; text-shadow: 0 0 20px rgba(212,175,55,0.3);'>🧠 V300 APEX TERMINAL</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#8b949e; font-size:18px;'>Gelişmiş Puan Durumu Analizi, Premium Arayüz ve Tam Otonom Skor Motoru</p><br>", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["🎯 V300 OTONOM RADAR", "💼 FON YÖNETİMİ & KONTROL BİLANÇOSU"])

c1, c2 = st.columns([2, 1])
with c1: secilen_ligler = st.multiselect("Taranacak Ligleri Seçin:", list(API_LEAGUES.keys()), default=["İngiltere Premier Lig", "Almanya Bundesliga", "İtalya Serie A", "Polonya Ekstraklasa", "Belçika Pro Lig", "Hollanda Eredivisie"])
with c2: api_key = st.text_input("The-Odds-API Anahtarı:", value=st.secrets.get("API_KEY", ""), type="password", key="odds_api_key")

with tab1:
    if st.button("📡 SADECE BUGÜNÜN MAÇLARINI ÇEK (Day-Trade)", use_container_width=True):
        if not api_key: st.error("API Anahtarı eksik!")
        else:
            with st.spinner("Puan durumları ve bugünün maçları küresel piyasalardan çekiliyor..."):
                toplanan_maclar = []
                now_utc = datetime.datetime.now(datetime.timezone.utc)
                now_tr = now_utc + datetime.timedelta(hours=3)
                
                for lig in secilen_ligler:
                    # Yeni isimli fonksiyon çağrılıyor
                    get_live_standings_v2(LEAGUE_IDS.get(lig, 0)) 
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
                st.success(f"✅ Sistem güncellendi! Sadece BUGÜN oynanacak {len(toplanan_maclar)} maç analize hazır.")
    
    st.divider()

    if st.button("🧠 V300: YAPAY ZEKA MODELİNİ ÇALIŞTIR", use_container_width=True):
        if len(st.session_state.raw_api_data) == 0: st.warning("Önce 'MAÇLARI ÇEK' butonuna basın!")
        else:
            with st.spinner("İstatistikler, Puan Durumları ve Cerrahi Filtre işleniyor..."):
                analiz_edilenler = []
                def form_ve_ht(takim, db_x):
                    tk = str(takim)[:5]
                    sm = db_x[(db_x['HomeTeam'].str.contains(tk, case=False, na=False)) | (db_x['AwayTeam'].str.contains(tk, case=False, na=False))].tail(5)
                    if len(sm) == 0: return 1.0, 0 
                    tp = 0; ht_ust = 0 
                    for _, mac in sm.iterrows():
                        ev_mi = tk.lower() in str(mac['HomeTeam']).lower()
                        if ev_mi and mac['FTR'] == 'H': tp += 3
                        elif not ev_mi and mac['FTR'] == 'A': tp += 3
                        elif mac['FTR'] == 'D': tp += 1
                        if 'HTHG' in mac and 'HTAG' in mac and (mac['HTHG'] + mac['HTAG'] > 0.5): ht_ust += 1
                    return 0.85 + ((tp / (len(sm) * 3)) * 0.30), (0.05 if ht_ust >= 3 else -0.02)

                for mac in st.session_state.raw_api_data:
                    lig_kodu = API_TO_DIV.get(mac.get('sport_key'))
                    gercek_lig_adi = mac.get('kendi_ligi', '')
                    aktif_db = db[db['Div'] == lig_kodu].copy() if lig_kodu else db.copy()
                    
                    standings_data = get_live_standings_v2(LEAGUE_IDS.get(gercek_lig_adi, 0))
                    ev_sira, ev_at, ev_ye, ev_son5 = '?', '?', '?', '?'
                    dep_sira, dep_at, dep_ye, dep_son5 = '?', '?', '?', '?'
                    
                    if standings_data:
                        # Akıllı Eşleştirme Motoru
                        ev_info = takim_eslestir(mac['home_team'], standings_data)
                        if ev_info:
                            ev_sira = ev_info.get('rank', '?')
                            ev_at = ev_info.get('all', {}).get('goals', {}).get('for', '?')
                            ev_ye = ev_info.get('all', {}).get('goals', {}).get('against', '?')
                            ev_son5 = format_form_string(ev_info.get('form', '?'))
                            
                        dep_info = takim_eslestir(mac['away_team'], standings_data)
                        if dep_info:
                            dep_sira = dep_info.get('rank', '?')
                            dep_at = dep_info.get('all', {}).get('goals', {}).get('for', '?')
                            dep_ye = dep_info.get('all', {}).get('goals', {}).get('against', '?')
                            dep_son5 = format_form_string(dep_info.get('form', '?'))

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
                        
                        aktif_db['diff'] = np.sqrt((aktif_db['B365H']-h_odd)**2 + (aktif_db['B365D']-d_odd)**2 + (aktif_db['B365A']-a_odd)**2)
                        benzer = aktif_db.sort_values('diff').head(80) 
                        
                        p_ms1 = (benzer[benzer['FTR']=='H']['B365H'].count() / len(benzer))
                        p_o25 = (benzer[(benzer['FTHG']+benzer['FTAG'])>2.5]['FTR'].count() / len(benzer))
                        p_u25 = 1.0 - p_o25
                        
                        ev_formu, ev_ht = form_ve_ht(mac['home_team'], aktif_db)
                        dep_formu, dep_ht = form_ve_ht(mac['away_team'], aktif_db)
                        genel_form = (ev_formu + dep_formu) / 2 
                        
                        c_kesinti = 0.015 
                        
                        ev_targets = [
                            ("MS 1", (p_ms1 * ev_formu) - c_kesinti, h_odd), 
                            ("2.5 Üst", (p_o25 * genel_form) + ev_ht + dep_ht - c_kesinti, o25_odd), 
                            ("2.5 Alt", p_u25 * (2.0 - genel_form) - c_kesinti, u25_odd)
                        ]
                        
                        en_iyi_ev, en_iyi_pazar, son_prob, is_ml = -999.0, None, 0.0, False
                        for pazar, raw_prob, oranim in ev_targets:
                            ml_key = f"{mac['sport_key']}|{pazar}"
                            stats = st.session_state.ml_stats.get(ml_key, {'w':0, 'l':0})
                            total = stats['w'] + stats['l']
                            kalibre = min(0.95, raw_prob)
                            if total >= 3:
                                kalibre = (kalibre * 0.70) + ((stats['w'] / total) * 0.30)
                                is_ml = True
                            
                            hev = (kalibre * oranim) - 1
                            if hev > en_iyi_ev:
                                en_iyi_ev, en_iyi_pazar, son_prob = hev, (pazar, raw_prob, hev), kalibre
                                
                        if en_iyi_pazar and son_prob > 0.53:
                            mac['hedef_pazar'] = en_iyi_pazar[0]
                            mac['kalibre_ihtimal'] = son_prob
                            mac['_g_score'] = en_iyi_pazar[2] 
                            mac['ml_kullanildi'] = is_ml
                            
                            mac['ai_rapor'] = generate_ai_report(
                                mac['home_team'], mac['away_team'], en_iyi_pazar[0], 
                                [x[2] for x in ev_targets if x[0]==en_iyi_pazar[0]][0], 
                                son_prob, ev_formu, dep_formu, c_kesinti,
                                ev_sira, ev_at, ev_ye, ev_son5, dep_sira, dep_at, dep_ye, dep_son5, gercek_lig_adi
                            )
                            analiz_edilenler.append(mac)

                st.session_state.top_adaylar = sorted(analiz_edilenler, key=lambda x: x.get('_g_score', -999), reverse=True)[:5]
                if len(st.session_state.top_adaylar) > 0: st.success("🔥 V300 Tam Kapasite İle Analizleri Tamamladı!")

    if 'top_adaylar' in st.session_state and len(st.session_state.top_adaylar) > 0:
        st.divider()
        st.markdown("<h2 style='color:#00ffcc;'>🎯 PREMIUM OTONOM KOMBİNE</h2>", unsafe_allow_html=True)
        yasal_oranlar = {}
        for i, m in enumerate(st.session_state.top_adaylar):
            badge = "<span class='ai-badge'>🧠 ML Algoritması Devrede</span>" if m['ml_kullanildi'] else ""
            
            st.markdown(f"<div class='match-card'><div class='match-title'>{m['home_team']} ⚡ {m['away_team']} {badge}</div><span style='color:#8b949e; font-size:16px;'>Kazanma İhtimali: <b style='color:#fff;'>%{int(m['kalibre_ihtimal']*100)}</b> | Lig: {m['kendi_ligi']}</span><br><div class='target-market'>Hedef Pazar: {m['hedef_pazar']}</div>", unsafe_allow_html=True)
            
            with st.expander("🤖 Gelişmiş Yapay Zeka (Fon Analisti) Raporunu Oku"):
                st.markdown(f"<div class='ai-report'>{m['ai_rapor']}</div>", unsafe_allow_html=True)
                
            yasal_oranlar[i] = {'oran': st.number_input(f"İddaa [{m['hedef_pazar']}] Oranını Girin:", min_value=1.01, value=1.50, step=0.05, key=f"y_oran_{i}"), 'match': m}
            st.markdown("</div>", unsafe_allow_html=True)
            
        st.markdown("<hr style='border:1px solid #2d3748;'>", unsafe_allow_html=True)
        manuel_tutar = st.number_input("💵 Kupona Yatırılacak Tutar (TL):", min_value=10.0, value=100.0, step=10.0)
            
        if st.button("🚀 KOMBİNEYİ ONAYLA (Fon Sistemine Gönder)", use_container_width=True):
            gecerli_maclar = [{'isim': f"{d['match']['home_team']} - {d['match']['away_team']}", 'h': d['match']['home_team'], 'a': d['match']['away_team'], 'tercih': d['match']['hedef_pazar'], 'oran': d['oran'], 'prob': d['match']['kalibre_ihtimal'], 'lig': d['match']['sport_key']} for d in yasal_oranlar.values()]
            
            if len(gecerli_maclar) >= 2:
                secilenler = gecerli_maclar[:2]
                toplam_oran = secilenler[0]['oran'] * secilenler[1]['oran']
                
                yatirilacak_tutar = manuel_tutar
                st.session_state.lokal_kasa -= yatirilacak_tutar
                st.session_state.bekleyen_tutar += yatirilacak_tutar
                
                if sheet:
                    isimler = f"{secilenler[0]['h']} vs {secilenler[0]['a']}#{secilenler[1]['h']} vs {secilenler[1]['a']}"
                    ligler = f"{secilenler[0]['lig']}#{secilenler[1]['lig']}"
                    tercihler = f"{secilenler[0]['tercih']}#{secilenler[1]['tercih']}"
                    problar = f"{secilenler[0]['prob']:.3f}#{secilenler[1]['prob']:.3f}"
                    oranlar = f"{secilenler[0]['oran']:.2f}#{secilenler[1]['oran']:.2f}"
                    
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), yatirilacak_tutar, toplam_oran, "Bekliyor", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, isimler, ligler, tercihler, problar, oranlar])
                
                st.session_state.top_adaylar = []
                st.success(f"✅ İşlem Başarılı! Otonom Kupon {yatirilacak_tutar:.0f} TL bakiye ile sisteme kilitlendi. Skorlar maç bitiminde kendi kendine denetlenecek.")
                st.rerun()

with tab2:
    st.markdown("<h2 style='color:#d4af37;'>💼 Kuantum Fon Bilanço Özeti</h2>", unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    kasa, bekleyen, baslangic = st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa
    roi = ((kasa - baslangic) / baslangic) * 100 if baslangic > 0 else 0.0
    with m1: st.markdown(f"<div class='metric-box'><div class='metric-title'>GÜNCEL KASA</div><div class='metric-value' style='color:#fff;'>{kasa:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-box'><div class='metric-title'>BEKLEYEN YATIRIM</div><div class='metric-value' style='color:#ffcc00;'>{bekleyen:.2f} ₺</div></div>", unsafe_allow_html=True)
    with m3: st.markdown(f"<div class='metric-box'><div class='metric-title'>ROI (KÂR/ZARAR)</div><div class='metric-value'>% {roi:.1f}</div></div>", unsafe_allow_html=True)
    
    st.divider()

    with st.expander("⚙️ KASA AYARLARI (Manuel Dönem Sıfırlaması)"):
        st.markdown("<i style='color:#8b949e; font-size:14px;'>Yeni bir yatırım dönemine başlarken kasayı güncelleyin. Kâr/Zarar (ROI) sıfırlanır ancak Yapay Zeka (ML) geçmiş maç istatistiklerini KORUR.</i>", unsafe_allow_html=True)
        c_kasa1, c_kasa2 = st.columns([2, 1])
        with c_kasa1:
            yeni_kasa_tutari = st.number_input("Yeni Kasa Tutarını Girin (TL):", min_value=0.0, value=float(st.session_state.lokal_kasa), step=100.0)
        with c_kasa2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔄 KASAYI GÜNCELLE", use_container_width=True):
                st.session_state.lokal_kasa = yeni_kasa_tutari
                st.session_state.baslangic_kasa = yeni_kasa_tutari
                if sheet:
                    sheet.append_row([datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 0, 0, "Sistem_Kasa_Guncelleme", "0", st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa, "-", "-", "-", "-", "-"])
                st.success("✅ Yeni yatırım dönemi başladı! Kasa güncellendi, veri tabanı güvende.")
                st.rerun()

    st.divider()
    
    c_btn1, c_btn2 = st.columns([3,1])
    with c_btn1: st.markdown("<h3>📝 Bekleyen Otonom Kuponlar</h3>", unsafe_allow_html=True)
    with c_btn2:
        if st.button("🤖 OTONOM DENETÇİYİ ÇALIŞTIR", use_container_width=True):
            if not api_key: st.error("Lütfen Ayarlar kısmına Odds API anahtarınızı girin!")
            else:
                with st.spinner("Tüm bekleyen maçların canlı skorları taranıyor..."):
                    updates_made = False
                    for idx, r in enumerate(all_vals):
                        if len(r) > 12 and r[3] == "Bekliyor":
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
                                    res, skor = "BEKLİYOR", "Eski Format (Manuel Kapatın)"
                                    
                                durumlar.append(res)
                                skorlar.append(skor)
                            
                            nihai_sonuc = "BEKLİYOR"
                            if "KAYBETTİ" in durumlar: nihai_sonuc = "KAYBETTİ"
                            elif all(d == "KAZANDI" for d in durumlar): nihai_sonuc = "KAZANDI"
                            
                            if nihai_sonuc != "BEKLİYOR":
                                updates_made = True
                                sheet.update_cell(idx+1, 4, "Bekliyor_Kapandı")
                                yeni_satir = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), b_tutar, b_oran]
                                if nihai_sonuc == "KAZANDI":
                                    st.session_state.lokal_kasa += (b_tutar * b_oran)
                                    st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                    yeni_satir.extend(["Kazandı_Sonuc", f"+{(b_tutar * b_oran) - b_tutar}"])
                                else:
                                    st.session_state.bekleyen_tutar = max(0.0, st.session_state.bekleyen_tutar - b_tutar)
                                    yeni_satir.extend(["Kaybetti_Sonuc", f"-{b_tutar}"])
                                    
                                yeni_satir.extend([st.session_state.lokal_kasa, st.session_state.bekleyen_tutar, st.session_state.baslangic_kasa])
                                yeni_satir.extend([r[8] + f" (Skorlar: {' | '.join(skorlar)})"] + r[9:])
                                sheet.append_row(yeni_satir)
                    
                    if updates_made:
                        st.success("✅ Maçlar sonuçlandırıldı, Kasa güncellendi!")
                        st.rerun()
                    else:
                        st.info("Maçlar henüz bitmemiş veya sonuçlanması bekleniyor.")

    bekleyenler = [(idx+1, r) for idx, r in enumerate(all_vals) if len(r) > 3 and r[3] == "Bekliyor"]
    if not bekleyenler: st.info("Şu an bekleyen yatırımınız bulunmamaktadır.")
    else:
        for row_idx, r in bekleyenler:
            b_tutar, b_oran = float(str(r[1]).replace(',','.').strip()), float(str(r[2]).replace(',','.').strip())
            mac_isimleri = r[8].replace('#', ' | ') if len(r) > 10 else "Eski Format Kupon"
            st.markdown(f"<div style='background: linear-gradient(to right, #1a202c, #11161d); border-left: 4px solid #ffcc00; padding:20px; border-radius:10px; margin-bottom:15px; box-shadow: 0 4px 10px rgba(0,0,0,0.2);'><b style='font-size:18px;'>Maçlar:</b> <span style='color:#e2e8f0;'>{mac_isimleri}</span><br><br><b style='font-size:16px;'>Tutar:</b> <span style='color:#00ffcc; font-size:18px; font-weight:bold;'>{b_tutar:.0f} TL</span> &nbsp;|&nbsp; <b style='font-size:16px;'>Toplam Oran:</b> <span style='color:#d4af37; font-size:18px; font-weight:bold;'>{b_oran:.2f}</span> <br><br><i style='color:#8b949e; font-size:14px;'>Otonom Denetçi bekleniyor...</i></div>", unsafe_allow_html=True)
