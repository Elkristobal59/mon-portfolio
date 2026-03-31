import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from google import genai

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Erreur: La variable d'environnement GEMINI_API_KEY est manquante.")
    exit(1)

client = genai.Client(api_key=API_KEY)
# On repasse sur 2.0 qui était détecté, mais on va être très économe
MODEL_ID = "gemini-2.0-flash"

def get_current_data_date():
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base_dir, '..', 'data', 'tldr.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("date")
    except: pass
    return None

def get_latest_newsletter_html():
    base_url = "https://tldr.tech/data/"
    today = datetime.now()
    current_saved_date = get_current_data_date()
    
    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        if current_saved_date == date_str:
            print(f"ℹ️ Déjà à jour ({date_str}).")
            exit(0)
        url = f"{base_url}{date_str}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and "<article" in response.text:
                print(f"✅ Newsletter trouvée : {date_str}")
                return response.text, date_str
        except: pass
    return None, None

def extract_articles(html):
    soup = BeautifulSoup(html, 'html.parser')
    articles_raw = soup.find_all('article', class_='mt-3')
    extracted = []
    for art in articles_raw:
        link_tag = art.find('a', class_='font-bold')
        if not link_tag: continue
        title = link_tag.get_text(strip=True)
        link = link_tag.get('href', '')
        if "(Sponsor)" in title or "fandf.co" in link: continue
        summary_div = art.find('div', class_='newsletter-html')
        summary = summary_div.get_text(strip=True) if summary_div else ""
        extracted.append({"title_en": title, "link": link, "summary_en": summary})
        # ON RÉDUIT À 6 ARTICLES pour tester si c'est un problème de quota par volume
        if len(extracted) >= 6: break
    return extracted

def process_with_ai(articles, date_str):
    if not articles: return "[]"
    
    # Texte minimaliste
    compact = ""
    for i, a in enumerate(articles):
        compact += f"#{i+1}: {a['title_en']}\n{a['summary_en'][:200]}\n"

    prompt = f"Traduis en JSON (titre, resume, lien, categorie:News|Tool|Deep Dive) ces articles du {date_str} (FR):\n{compact}"
    
    print(f"🚀 Essai avec {MODEL_ID} ({len(articles)} articles)...")
    
    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        res = response.text.strip()
        return res.replace("```json", "").replace("```", "").strip()
    except Exception as e:
        print(f"❌ Erreur avec {MODEL_ID}: {e}")
        
        # DIAGNOSTIC : Si erreur, on liste les modèles dispo pour trouver le bon nom
        print("\n--- DIAGNOSTIC DES MODÈLES DISPONIBLES ---")
        try:
            for m in client.models.list():
                if "flash" in m.name.lower():
                    print(f"Modèle dispo : {m.name}")
        except:
            print("Impossible de lister les modèles.")
            
        if "429" in str(e):
            print("Quota toujours épuisé.")
            exit(0)
        raise e

def main():
    html, date_str = get_latest_newsletter_html()
    if not html: return
    articles = extract_articles(html)
    json_data = process_with_ai(articles, date_str)
    try:
        data = json.loads(json_data)
        out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'tldr.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump({"date": date_str, "articles": data}, f, indent=4, ensure_ascii=False)
        print(f"✅ OK pour {date_str}")
    except:
        print("Erreur JSON")
        exit(1)

if __name__ == "__main__":
    main()