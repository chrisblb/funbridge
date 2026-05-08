#!/usr/bin/env python3
"""
Met à jour automatiquement les tarifs de recharge VE dans recharge-comparatif.html
en interrogeant Claude (avec recherche web) pour obtenir les prix à jour.
"""
import anthropic
import json
import re
import sys
from datetime import date


HTML_PATH = "recharge-comparatif.html"


def load_html():
    with open(HTML_PATH, encoding="utf-8") as f:
        return f.read()


def extract_current_data(html):
    """Extrait le bloc DEFAULT_DATA par comptage d'accolades."""
    lines = html.split("\n")
    start = None
    for i, line in enumerate(lines):
        if "const DEFAULT_DATA = {" in line:
            start = i
            break
    if start is None:
        raise ValueError("DEFAULT_DATA introuvable dans le fichier HTML")

    depth = 0
    end = start
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if i > start and depth == 0:
            end = i
            break

    block = "\n".join(lines[start:end + 1])
    json_str = block[len("const DEFAULT_DATA = "):]
    if json_str.endswith(";"):
        json_str = json_str[:-1]
    return json.loads(json_str)


def replace_data_in_html(html, new_data):
    """Remplace le bloc DEFAULT_DATA par les nouvelles données."""
    lines = html.split("\n")
    start = None
    for i, line in enumerate(lines):
        if "const DEFAULT_DATA = {" in line:
            start = i
            break

    depth = 0
    end = start
    for i in range(start, len(lines)):
        depth += lines[i].count("{") - lines[i].count("}")
        if i > start and depth == 0:
            end = i
            break

    new_json = json.dumps(new_data, ensure_ascii=False, indent=2)
    new_lines = lines[:start] + [f"const DEFAULT_DATA = {new_json};"] + lines[end + 1:]
    return "\n".join(new_lines)


def fetch_updated_prices(current_data):
    """Appelle Claude avec recherche web pour obtenir les tarifs à jour."""
    client = anthropic.Anthropic()

    operators_list = "\n".join(
        f"- {op['name']} — {op['offerName']}"
        for op in current_data["operators"]
    )

    current_json = json.dumps(current_data, ensure_ascii=False, indent=2)

    prompt = f"""Tu dois mettre à jour un comparatif de tarifs de recharge pour véhicules électriques en France.

Recherche sur internet les tarifs **actuels** (date d'aujourd'hui : {date.today()}) pour chacun de ces opérateurs/offres :

{operators_list}

Pour chaque offre, vérifie :
- Le prix de l'abonnement mensuel
- Le prix au kWh (par type de borne et réseau)
- Le prix de la carte physique

Voici la structure actuelle des données (JSON) — conserve exactement le même format, les mêmes couleurs (`color`) et initiales (`initials`), et mets à jour uniquement les prix et notes si tu trouves des changements confirmés :

```json
{current_json}
```

Retourne UNIQUEMENT l'objet JSON mis à jour, sans aucun texte avant ou après, sans bloc de code markdown.
La clé `lastUpdate` doit valoir "{date.today()}".
Si tu n'as pas de confirmation d'un changement de prix, conserve la valeur actuelle."""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )

    for block in response.content:
        if block.type == "text":
            text = block.text.strip()
            # Retirer un éventuel bloc markdown ```json ... ```
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            return json.loads(text)

    raise ValueError("Aucun JSON valide dans la réponse de Claude")


def main():
    print("Lecture du fichier HTML...")
    html = load_html()

    print("Extraction des données actuelles...")
    current_data = extract_current_data(html)
    print(f"  → Données du {current_data['lastUpdate']}, {len(current_data['operators'])} offres.")

    print("Recherche des tarifs à jour via Claude...")
    new_data = fetch_updated_prices(current_data)
    print(f"  → Données mises à jour au {new_data['lastUpdate']}, {len(new_data['operators'])} offres.")

    print("Mise à jour du fichier HTML...")
    new_html = replace_data_in_html(html, new_data)

    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("✓ Terminé.")


if __name__ == "__main__":
    main()
