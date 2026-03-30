import os
import re
import json
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import google.generativeai as genai

# Configuration de Gemini
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("Erreur: La variable d'environnement GEMINI_API_KEY est manquante.")
    exit(1)

genai.configure(api_key=API_KEY)
# On utilise le modèle le plus rapide et gratuit pour le texte
model = genai.GenerativeModel('gemini-1.5-flash')

def get_latest_newsletter_html():
    """Tente de récupérer la dernière newsletter en cherchant jusqu'à 7 jours en arrière."""
    base_url = "https://tldr.tech/data/"
    today = datetime.now()
    
    for i in range(7):
        date_str = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        url = f"{base_url}{date_str}"
        print(f"Vérification de l'URL : {url}")
        
        response = requests.get(url)
        if response.status_code == 200:
            print(f"Newsletter trouvée pour le {date_str} !")
            return response.text, date_str
            
    print("Aucune newsletter trouvée dans les 7 derniers jours.")
    return None, None

def extract_content(html):
    """Extrait le texte de la page HTML de manière brute pour l'envoyer à l'IA."""
    soup = BeautifulSoup(html, 'html.parser')
    # Supprimer les balises script et style
    for script_or_style in soup(["script", "style"]):
        script_or_style.extract()
    return soup.get_text(separator="\n", strip=True)

def process_with_ai(text_content, date_str):
    """Envoie le texte à Gemini pour traduction et formatage JSON strict."""
    prompt = f"""
    Voici le texte extrait de la newsletter anglophone 'TLDR Data' datée du {date_str}.
    Ta mission est d'extraire les articles de fond (Oublie les annonces de sponsors, le blabla de début de mail ou les offres d'emploi brutes).
    
    Pour chaque article pertinent extrait :
    1. Traduis le titre en français.
    2. Traduis le résumé (le corps du texte) en français d'une manière professionnelle et concise.
    3. Trouve le lien original de la source (URL) s'il y en a un.
    4. Attribue une catégorie (ex: "News", "Deep Dive", "Tutoriel", "Tool").
    
    Tu DOIS me répondre UNIQUEMENT avec un tableau JSON valide (pas de markdown `json`, que du code JSON pur) avec cette structure exacte pour chaque article :
    [
        {{
            "titre": "Le titre traduit",
            "resume": "Le résumé traduit",
            "lien": "https://...",
            "categorie": "Deep Dive"
        }}
    ]
    Voici le texte de la newsletter :
    {text_content}
    """
    
    print("Envoi du contenu à Gemini pour traduction...")
    response = model.generate_content(prompt)
    
    # Nettoyage si le modèle répond avec des blocs Markdown
    result = response.text.strip()
    if result.startswith("```json"):
        result = result.replace("```json", "", 1)
    if result.endswith("```"):
        result = result[::-1].replace("```", "", 1)[::-1]
        
    return result.strip()

def main():
    # 1. Récupérer le HTML
    html, date_str = get_latest_newsletter_html()
    if not html:
        exit(1)
        
    # 2. Extraire le texte utile
    text = extract_content(html)
    
    # 3. Traiter avec l'IA
    json_data = process_with_ai(text, date_str)
    
    # 4. Vérifier que c'est un JSON valide et ajouter la date
    try:
        articles = json.loads(json_data)
        final_output = {
            "date": date_str,
            "articles": articles
        }
        
        # S'assurer que le dossier data existe
        os.makedirs(os.path.join(os.path.dirname(__file__), '..', 'data'), exist_ok=True)
        out_path = os.path.join(os.path.dirname(__file__), '..', 'data', 'tldr.json')
        
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(final_output, f, indent=4, ensure_ascii=False)
            
        print(f"Succès ! {len(articles)} articles sauvegardés dans {out_path}")
        
    except json.JSONDecodeError as e:
        print("Erreur : L'IA n'a pas renvoyé un JSON valide.")
        print("Réponse brute reçue :", json_data)
        exit(1)

if __name__ == "__main__":
    main()
