import os
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from google import genai # Nouveau client SDK Gemini 3.0

# Configuration du nouveau client
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Erreur: La variable d'environnement GEMINI_API_KEY est manquante.")
    exit(1)

# Initialisation du client moderne
client = genai.Client(
    api_key=API_KEY,
    http_options={'api_version': 'v1'} # Force la version stable
)

MODEL_ID = "gemini-1.5-flash"

def get_latest_newsletter_html():
    """Tente de récupérer la dernière newsletter."""
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
    """Extrait le texte brut."""
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup(["script", "style"]):
        s.extract()
    return soup.get_text(separator="\n", strip=True)

def process_with_ai(text_content, date_str):
    """Utilise le nouveau SDK avec le support natif du format JSON."""
    prompt = f"""
    Voici la newsletter 'TLDR Data' du {date_str}. 
    Extrait les articles de fond (News, tutoriels, outils).
    Ignore les sponsors et les jobs.
    
    Format de réponse attendu (JSON uniquement) :
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
    
    # Utilisation de generate_content avec configuration de réponse JSON
    response = client.models.generate_content(
        model=MODEL_ID,
        contents=prompt,
        config={
            'response_mime_type': 'application/json'
        }
    )
    
    return response.text

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
        
        # Chemin relatif propre
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_path = os.path.join(base_dir, '..', 'data', 'tldr.json')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
            
        print(f"Succès ! {len(articles)} articles sauvegardés.")
        
    except json.JSONDecodeError:
        print("Erreur : Réponse JSON invalide.")
        print(json_data)
        exit(1)

if __name__ == "__main__":
    main()