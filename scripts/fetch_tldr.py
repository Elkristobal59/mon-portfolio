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

# Initialisation standard (la plus stable)
client = genai.Client(api_key=API_KEY)
MODEL_ID = "gemini-2.0-flash"

def get_latest_newsletter_html():
    """Récupère le HTML de la newsletter la plus récente (7 derniers jours)."""
    base_url = "https://tldr.tech/data/"
    today = datetime.now()
    
    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"{base_url}{date_str}"
        print(f"Vérification de l'URL : {url}")
        
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                print(f"Newsletter trouvée pour le {date_str} !")
                return response.text, date_str
        except requests.RequestException as e:
            print(f"Erreur lors de la requête : {e}")
            
    print("Aucune newsletter trouvée.")
    return None, None

def extract_content(html):
    """Nettoie le HTML pour ne garder que le texte utile."""
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup(["script", "style"]):
        s.extract()
    return soup.get_text(separator="\n", strip=True)

def process_with_ai(text_content, date_str):
    """Demande à l'IA d'extraire et traduire les articles en JSON."""
    prompt = f"""
    Voici la newsletter 'TLDR Data' du {date_str}. 
    Extrait les articles de fond (News, tutoriels, outils).
    Ignore les sponsors et les jobs.
    
    IMPORTANT : Ta réponse doit être uniquement un tableau JSON valide, sans texte avant ou après.
    
    Format attendu :
    [
        {{
            "titre": "Traduction française du titre",
            "resume": "Résumé concis en français",
            "lien": "URL source",
            "categorie": "News|Tutoriel|Tool|Deep Dive"
        }}
    ]
    
    Contenu :
    {text_content}
    """
    
    print(f"Envoi à {MODEL_ID}...")
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt
        )
        
        # Nettoyage des balises Markdown ```json si présentes
        result = response.text.strip()
        if result.startswith("```json"):
            result = result.replace("```json", "", 1)
        if result.endswith("```"):
            result = result[::-1].replace("```", "", 1)[::-1]
            
        return result.strip()
        
    except Exception as e:
        # Gestion intelligente du quota (Error 429)
        if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
            print("\n⚠️ QUOTA ÉPUISÉ : Le script s'arrête proprement pour aujourd'hui.")
            exit(0) # Sortie propre sans erreur GitHub
        print(f"Erreur lors de la génération : {e}")
        raise e

def main():
    html, date_str = get_latest_newsletter_html()
    if not html:
        exit(1)
        
    text = extract_content(html)
    json_data = process_with_ai(text, date_str)
    
    try:
        articles = json.loads(json_data)
        final_output = {
            "date": date_str,
            "articles": articles
        }
        
        # Gestion propre des chemins de fichiers
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(base_dir, '..', 'data', 'tldr.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
            
        print(f"✅ Succès ! {len(articles)} articles sauvegardés dans data/tldr.json")
        
    except json.JSONDecodeError:
        print("❌ Erreur : L'IA n'a pas renvoyé un JSON valide.")
        print("Réponse reçue :", json_data)
        exit(1)

if __name__ == "__main__":
    main()