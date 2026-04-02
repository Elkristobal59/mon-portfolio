import os
import json
import requests
import time
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from google import genai
from google.genai import errors

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Erreur: La variable d'environnement GEMINI_API_KEY est manquante.")
    exit(1)

# Initialisation du client
client = genai.Client(api_key=API_KEY)

# Modèles
PRIMARY_MODEL = "gemini-3-flash-preview"
FALLBACK_MODEL = "gemini-3-flash"

def get_current_data_date():
    """Récupère la date de la dernière newsletter enregistrée dans le JSON."""
    try:
        base_dir = os.path.dirname(os.path.abspath(_file_))
        path = os.path.join(base_dir, '..', 'data', 'tldr.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("date")
    except Exception as e:
        print(f"Note: Impossible de lire la date actuelle ({e})")
    return None

def get_latest_newsletter_html():
    """Récupère le HTML de la newsletter la plus récente (7 derniers jours)."""
    base_url = "https://tldr.tech/data/"
    today = datetime.now()
    
    current_saved_date = get_current_data_date()
    
    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        
        if current_saved_date == date_str:
            print(f"ℹ️ La newsletter du {date_str} est déjà à jour. Arrêt du script.")
            exit(0)

        url = f"{base_url}{date_str}"
        print(f"Vérification de l'URL : {url}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                if "<article" in response.text:
                    print(f"✅ Newsletter valide trouvée pour le {date_str} !")
                    return response.text, date_str
                else:
                    print(f"⚠️ Page d'attente pour le {date_str}. Essai du jour précédent...")
        except requests.RequestException as e:
            print(f"Erreur lors de la requête : {e}")
            
    print("❌ Aucune nouvelle newsletter valide trouvée.")
    return None, None

def extract_articles(html):
    """Extrait les articles (Titre, Lien, Résumé EN) et ignore les sponsors."""
    soup = BeautifulSoup(html, 'html.parser')
    articles_raw = soup.find_all('article', class_='mt-3')
    
    extracted = []
    for art in articles_raw:
        link_tag = art.find('a', class_='font-bold')
        if not link_tag:
            continue
            
        title = link_tag.get_text(strip=True)
        link = link_tag.get('href', '')
        
        if "(Sponsor)" in title or "fandf.co" in link:
            continue
            
        summary_div = art.find('div', class_='newsletter-html')
        summary = summary_div.get_text(strip=True) if summary_div else ""
        
        if title and link:
            extracted.append({
                "title_en": title,
                "link": link,
                "summary_en": summary
            })
        
        if len(extracted) >= 12:
            break
            
    return extracted

def call_gemini_api(model_id, prompt):
    """Effectue l'appel réel à l'API Gemini."""
    response = client.models.generate_content(
        model=model_id,
        contents=prompt
    )
    result = response.text.strip()
    # Nettoyage du Markdown si présent
    if result.startswith("json"):
        result = result.replace("json", "", 1)
    if result.endswith(""):
        result = result[::-1].replace("", "", 1)[::-1]
    return result.strip()

def process_with_ai(articles, date_str):
    """Traduction et synthèse via Gemini avec gestion du Hot Swap."""
    if not articles:
        return "[]"

    compact_content = ""
    for i, art in enumerate(articles):
        compact_content += f"ID:{i+1}\nT:{art['title_en']}\nS:{art['summary_en']}\nL:{art['link']}\n\n"

    prompt = f"""
    Voici les articles TLDR Data du {date_str}.
    Traduis titres et résumés en Français de manière concise.
    Catégorise chaque article : News, Tutoriel, Tool, ou Deep Dive.

    IMPORTANT : Réponds UNIQUEMENT avec un tableau JSON valide.
    
    Format :
    [
        {{
            "titre": "Titre traduit",
            "resume": "Résumé court FR",
            "lien": "URL",
            "categorie": "Catégorie"
        }}
    ]

    Contenu :
    {compact_content}
    """
    
    print(f"🚀 Tentative de traduction via {PRIMARY_MODEL}...")
    
    try:
        # Tentative 1 : Modèle Preview
        return call_gemini_api(PRIMARY_MODEL, prompt)
        
    except errors.ServerError as e:
        # Si erreur 503 (Surcharge), on tente le Hot Swap
        if "503" in str(e) or "UNAVAILABLE" in str(e):
            print(f"⚠️ {PRIMARY_MODEL} surchargé (503). Pause de 5s et basculement vers {FALLBACK_MODEL}...")
            time.sleep(5)
            try:
                return call_gemini_api(FALLBACK_MODEL, prompt)
            except Exception as e2:
                print(f"❌ Échec du modèle de secours : {e2}")
                raise e2
        raise e
        
    except Exception as e:
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ QUOTA ÉPUISÉ : Gemini ne répond plus aujourd'hui.")
            exit(0)
        print(f"❌ Erreur Gemini critique : {e}")
        raise e

def main():
    html, date_str = get_latest_newsletter_html()
    if not html:
        return
        
    articles_list = extract_articles(html)
    if not articles_list:
        print("❌ Aucun article exploitable trouvé.")
        exit(0)

    json_data = process_with_ai(articles_list, date_str)
    
    try:
        articles = json.loads(json_data)
        final_output = {
            "date": date_str,
            "articles": articles
        }
        
        base_dir = os.path.dirname(os.path.abspath(_file_))
        out_path = os.path.join(base_dir, '..', 'data', 'tldr.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Succès ! {len(articles)} articles sauvegardés pour le {date_str}")
        
    except json.JSONDecodeError:
        print("❌ Erreur : L'IA n'a pas renvoyé un JSON valide.")
        print("Réponse reçue :", json_data)
        exit(1)

if _name_ == "_main_":
    main()
