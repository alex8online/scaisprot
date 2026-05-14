import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor
import logging
import re

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SkyScraper:
    def __init__(self):
        self.base_url = "https://guidatv.org"
        self.start_url = "https://guidatv.org/canali"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        # Questa regex identifica "X min", "X ore" e tutto ciò che segue (inclusi i pipe |)
        self.clean_regex = re.compile(r'\s+\d+\s+(min|ore).*|(?:\s*\|.*)', re.IGNORECASE)

        self.target_map = {
            "Sport": [
                {"u": "sky-sport-24", "n": "Sky Sport 24"},
                {"u": "sky-sport-uno", "n": "Sky Sport Uno"},
                {"u": "sky-sport-calcio", "n": "Sky Sport Calcio"},
                {"u": "sky-sport-tennis", "n": "Sky Sport Tennis"},
                {"u": "sky-sport-f1", "n": "Sky Sport F1"},
                {"u": "sky-sport-motogp", "n": "Sky Sport MotoGP"},
                {"u": "sky-sport-basket", "n": "Sky Sport Basket"},
                {"u": "sky-sport-arena", "n": "Sky Sport Arena"},
                {"u": "sky-sport-max", "n": "Sky Sport Max"},
                {"u": "sky-sport-mix", "n": "Sky Sport Mix"},
                {"u": "sky-sport-golf", "n": "Sky Sport Golf"},
                {"u": "sky-sport-action", "n": "Sky Sport Legend"},
                {"u": "eurosport-1", "n": "Eurosport 1"},
                {"u": "eurosport-2", "n": "Eurosport 2"}
            ],
            "Cinema": [
                {"u": "sky-cinema-uno", "n": "Sky Cinema Uno"},
                {"u": "sky-cinema-uno-plus-24", "n": "Sky Cinema Uno +24"},
                {"u": "sky-cinema-collection", "n": "Sky Cinema Collection"},
                {"u": "sky-cinema-stories", "n": "Sky Cinema Stories"},
                {"u": "sky-cinema-family", "n": "Sky Cinema Family"},
                {"u": "sky-cinema-action", "n": "Sky Cinema Action"},
                {"u": "sky-cinema-suspense", "n": "Sky Cinema Suspense"},
                {"u": "sky-cinema-romance", "n": "Sky Cinema Romance"},
                {"u": "sky-cinema-drama", "n": "Sky Cinema Drama"},
                {"u": "sky-cinema-comedy", "n": "Sky Cinema Comedy"}
            ],
            "Intrattenimento": [
                {"u": "sky-uno", "n": "Sky Uno"},
                {"u": "sky-uno-plus-1", "n": "Sky Uno +1"},
                {"u": "sky-atlantic", "n": "Sky Atlantic"},
                {"u": "sky-atlantic-plus-1", "n": "Sky Atlantic +1"},
                {"u": "sky-serie", "n": "Sky Serie"},
                {"u": "sky-investigation", "n": "Sky Investigation"},
                {"u": "sky-crime", "n": "Sky Crime"},
                {"u": "sky-adventure", "n": "Sky Adventure"}, # Aggiunto come richiesto
                {"u": "mtv", "n": "MTV"},
                {"u": "comedy-central", "n": "Comedy Central"}
            ],
            "Documentari": [
                {"u": "sky-arte", "n": "Sky Arte"},
                {"u": "sky-documentaries", "n": "Sky Documentaries"},
                {"u": "sky-nature", "n": "Sky Nature"},
                {"u": "discovery-channel", "n": "Discovery Channel"},
                {"u": "national-geographic", "n": "National Geographic"},
                {"u": "history-channel", "n": "History Channel"}
            ],
            "News": [
                {"u": "sky-tg24", "n": "Sky TG 24"},
                {"u": "sky-meteo-24", "n": "Sky Meteo 24"}
            ]
        }

    def _clean_title(self, title):
        """Rimuove durata, categoria e descrizione dal titolo in modo aggressivo."""
        if not title:
            return "N/A"
        # Rimuove tutto ciò che segue la durata (es. "15 min") o il separatore pipe/trattino
        cleaned = self.clean_regex.split(title)[0]
        # Pulizia residua per caratteri speciali e spazi
        cleaned = cleaned.split('|')[0].split('—')[0].strip()
        return cleaned

    def get_matched_channels(self):
        """Trova gli URL reali sul sito guidatv.org basandosi sulla mappa target."""
        try:
            res = self.session.get(self.start_url, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            all_links = soup.find_all('a', href=True)
            
            matched = []
            for cat, ch_list in self.target_map.items():
                for target in ch_list:
                    # Puliamo l'ID target per il matching (rimuoviamo trattini)
                    target_id = target['u'].replace('-', '').lower()
                    
                    found = False
                    for link in all_links:
                        href = link['href']
                        if href.startswith('/canali/'):
                            # Puliamo lo slug del link (es. /canali/sky-adventure -> skyadventure)
                            slug = href.split('/')[-1].replace('-', '').lower()
                            
                            # Matching flessibile
                            if target_id in slug or slug in target_id:
                                matched.append({
                                    "nome": target['n'],
                                    "url": self.base_url + href,
                                    "categoria": cat
                                })
                                found = True
                                break
                    
                    # Fallback specifico per Adventure se non trovato con prefisso sky
                    if not found and target['u'] == "sky-adventure":
                         for link in all_links:
                            if "adventure" in link['href'].lower():
                                matched.append({
                                    "nome": target['n'],
                                    "url": self.base_url + link['href'],
                                    "categoria": cat
                                })
                                break

            return matched
        except Exception as e:
            logger.error(f"Errore nel recupero canali: {e}")
            return []

    def _extract_programs(self, soup):
        """Estrae i dati dei programmi preferendo il JSON strutturato (__NEXT_DATA__)."""
        script = soup.find('script', id='__NEXT_DATA__')
        if script:
            try:
                data = json.loads(script.string)
                props = data.get('props', {}).get('pageProps', {})
                programs_list = (props.get('initialData', {}).get('channel', {}).get('programs', []) or 
                                 props.get('programs', []) or [])
                
                extracted = []
                for p in programs_list:
                    # Estrazione ora
                    ora = p.get('startTime') or p.get('ora') or ""
                    if 'T' in str(ora):
                        ora = ora.split('T')[1][:5]
                    else:
                        ora = str(ora)[:5]
                    
                    # Estrazione titolo con pulizia
                    titolo_raw = p.get('title') or p.get('titolo') or "N/A"
                    
                    if ora and titolo_raw:
                        extracted.append({
                            "ora": ora, 
                            "titolo": self._clean_title(titolo_raw)
                        })
                if extracted:
                    return extracted
            except Exception:
                pass

        # Fallback parsing HTML se il JSON fallisce
        extracted = []
        items = soup.find_all(['div', 'li'], class_=True)
        for item in items:
            text = item.get_text(" ", strip=True)
            if len(text) > 5 and ":" in text[:6]:
                parts = text.split(" ", 1)
                ora = parts[0].strip()
                if len(ora) == 5 and ora[2] == ":":
                    titolo_raw = parts[1].strip() if len(parts) > 1 else "Programma"
                    extracted.append({
                        "ora": ora, 
                        "titolo": self._clean_title(titolo_raw)
                    })
        return extracted

    def scrape_channel(self, ch):
        """Scarica e processa un singolo canale."""
        try:
            res = self.session.get(ch['url'], timeout=10)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, 'html.parser')
            programs = self._extract_programs(soup)
            
            # Rimuove duplicati basati su ora e titolo
            seen = set()
            unique_progs = []
            for p in programs:
                key = f"{p['ora']}-{p['titolo']}"
                if key not in seen:
                    unique_progs.append(p)
                    seen.add(key)

            return {
                "canale": ch['nome'],
                "categoria": ch['categoria'],
                "programmi": unique_progs[:12], # Prendiamo i prossimi 12 eventi
                "aggiornato": datetime.now().strftime("%H:%M")
            }
        except Exception:
            return None

    def run(self):
        start_time = time.time()
        channels = self.get_matched_channels()
        
        if not channels:
            logger.warning("Nessun canale trovato. Verifica la connessione o l'URL.")
            return

        logger.info(f"Trovati {len(channels)} canali da scansionare...")

        # Utilizziamo un pool di thread per velocizzare il caricamento dei 44 canali
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.scrape_channel, channels))
            
        # Filtriamo i risultati nulli
        final_data = [r for r in results if r is not None]
        
        # Salvataggio su file JSON
        with open('guida_tv_sky.json', 'w', encoding='utf-8') as f:
            json.dump(final_data, f, ensure_ascii=False, indent=4)
            
        duration = round(time.time() - start_time, 1)
        logger.info(f"Fatto! {len(final_data)} canali salvati in {duration}s.")

if __name__ == "__main__":
    scraper = SkyScraper()
    scraper.run()
