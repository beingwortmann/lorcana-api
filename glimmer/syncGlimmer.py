#!/usr/bin/env python3
import json
import os
import pathlib
import sqlite3
import urllib.request
import urllib.parse

def download_catalog():
    # Token aus Umgebungsvariablen (Secret) abrufen
    token_auth = os.environ['LORCANA_SECRET_TOKEN'].strip()
    token_request = urllib.request.Request(
        "https://sso.ravensburger.de/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": token_auth, "User-Agent": ""}
    )
    with urllib.request.urlopen(token_request) as f:
        token = json.loads(f.read().decode("utf-8"))
    
    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    catalog_dir.mkdir(exist_ok=True)
    
    for lang in ("de", "en", "fr", "it"):
        print(f"Downloading {lang} catalog")
        catalog_auth = f"{token['token_type']} {token['access_token']}"
        catalog_request = urllib.request.Request(
            f"https://api.lorcana.ravensburger.com/v2/catalog/{lang}",
            headers={"Authorization": catalog_auth, "User-Agent": ""}
        )
        with urllib.request.urlopen(catalog_request) as f:
            contents = json.loads(f.read().decode("utf-8"))
    
        lang_dir = catalog_dir / lang
        lang_dir.mkdir(exist_ok=True)
    
        cards_dir = lang_dir / "cards"
        cards_dir.mkdir(exist_ok=True)
    
        for card_type in contents["cards"]:
            card_type_dir = cards_dir / card_type
            card_type_dir.mkdir(exist_ok=True)
            for card in contents["cards"][card_type]:
                if "abilities" in card:
                    card["abilities"].sort()
                # Speichere jede Karte als JSON-Datei. Der Dateiname basiert auf dem card_identifier.
                filename = card.get("card_identifier", "").replace("/", "_").replace(" ", "_") + ".json"
                with (card_type_dir / filename).open("w", encoding="utf-8") as out:
                    json.dump(card, out, indent=2, ensure_ascii=False)
    
        # Katalog ohne Karten speichern
        del contents["cards"]
        with (lang_dir / "catalog-no-cards.json").open("w", encoding="utf-8") as out:
            json.dump(contents, out, indent=2, ensure_ascii=False)

def extract_chapter(card_identifier):
    """
    Extrahiert die Kapitelnummer aus dem card_identifier.
    Es wird der letzte Token (nach dem Sprachcode) verwendet.
    Ist dieser nicht rein numerisch, wird "0" zurückgegeben.
    Beispiel: "25/204 IT 6" -> "6", "25/204 EN Q1" -> "0"
    """
    tokens = card_identifier.strip().split()
    if tokens:
        candidate = tokens[-1]
        if candidate.isdigit():
            return candidate
    return "0"

def process_catalog_and_update_db(catalog_dir, thumbnails_dir, db_path):
    # Erstelle/öffne die Datenbank mit dem gewünschten Namen
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        magic_ink_colors TEXT,
        ink_convertible INTEGER,
        rarity TEXT,
        type TEXT,
        card_identifier TEXT,
        card_sets TEXT,
        number INTEGER,
        author TEXT,
        name TEXT,
        subtitle TEXT,
        ink_cost TEXT,
        quest_value TEXT,
        strength TEXT,
        willpower TEXT,
        flavor_text TEXT,
        rules_text TEXT,
        image_url TEXT,
        fullName TEXT
    )
    ''')
    conn.commit()
    
    for lang_dir in catalog_dir.iterdir():
        if lang_dir.is_dir():
            language = lang_dir.name
            print(f"Processing catalog for language: {language}")
            cards_dir = lang_dir / "cards"
            if not cards_dir.exists():
                continue
            for category_dir in cards_dir.iterdir():
                if category_dir.is_dir() and category_dir.name in {"actions", "characters", "items", "locations"}:
                    card_type = category_dir.name  # Wird als "type" in die DB übernommen
                    for json_file in category_dir.glob("*.json"):
                        try:
                            with json_file.open("r", encoding="utf-8") as f:
                                card = json.load(f)
                        except Exception as e:
                            print(f"Error reading {json_file}: {e}")
                            continue
                        
                        # Hier: Extrahiere die Farbe und formatiere sie:
                        raw_colors = card.get("magic_ink_colors", "")
                        if isinstance(raw_colors, list):
                            processed_colors = " / ".join([str(c).capitalize() for c in raw_colors])
                        else:
                            processed_colors = str(raw_colors).capitalize()
                        magic_ink_colors = processed_colors
                        
                        ink_convertible = 1 if card.get("ink_convertible", False) else 0
                        rarity = card.get("rarity", "")
                        typ = card_type
                        card_identifier = card.get("card_identifier", "")
                        # Für card_sets: Wähle den niedrigsten numerischen Wert (falls möglich)
                        card_sets_raw = card.get("card_sets", [])
                        card_sets = ""
                        if isinstance(card_sets_raw, list) and card_sets_raw:
                            try:
                                numbers = [int(x) for x in card_sets_raw if str(x).isdigit()]
                                if numbers:
                                    card_sets = str(min(numbers))
                                else:
                                    card_sets = str(card_sets_raw[0])
                            except Exception:
                                card_sets = str(card_sets_raw[0])
                        else:
                            card_sets = str(card_sets_raw)
                        # number: Verwende den Teil vor dem "/" in card_identifier
                        num = 0
                        try:
                            parts = card_identifier.split("/")
                            if parts:
                                num = int(parts[0])
                        except Exception:
                            num = 0
                        author = card.get("author", "")
                        name_field = card.get("name", "")
                        subtitle_field = card.get("subtitle", "")
                        ink_cost = card.get("ink_cost", "")
                        quest_value = card.get("quest_value", "")
                        strength = card.get("strength", "")
                        willpower = card.get("willpower", "")
                        flavor_text = card.get("flavor_text", "")
                        rules_text = card.get("rules_text", "")
                        # image_url: Wähle den Link aus image_urls mit height == 512
                        image_url = ""
                        image_urls = card.get("image_urls", [])
                        if isinstance(image_urls, list):
                            for entry in image_urls:
                                if isinstance(entry, dict) and entry.get("height") == 512:
                                    image_url = entry.get("url", "")
                                    break
                        elif isinstance(image_urls, dict):
                            for key, entry in image_urls.items():
                                if isinstance(entry, dict) and entry.get("height") == 512:
                                    image_url = entry.get("url", "")
                                    break
                        fullName = f"{name_field} - {subtitle_field}"
                        
                        cursor.execute('''
                        INSERT INTO cards (
                            magic_ink_colors, ink_convertible, rarity, type, card_identifier, card_sets, number, author, name, subtitle, ink_cost, quest_value, strength, willpower, flavor_text, rules_text, image_url, fullName
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ''', (magic_ink_colors, ink_convertible, rarity, typ, card_identifier, card_sets, num, author, name_field, subtitle_field, ink_cost, quest_value, strength, willpower, flavor_text, rules_text, image_url, fullName))
                        conn.commit()
                        
                        # Prüfe anhand des card_identifier, ob nach dem Slash ein Buchstabe folgt.
                        parts = card_identifier.split("/")
                        if len(parts) > 1 and parts[1] and not parts[1][0].isdigit():
                            print(f"Skipping thumbnail download for {card_identifier} due to letter in identifier.")
                        # Falls Sprache EN und ein Bild-Link vorhanden ist, lade das Thumbnail herunter
                        elif language == "en" and image_url:
                            try:
                                chapter = extract_chapter(card_identifier)
                                if not chapter.isdigit():
                                    chapter = "0"
                                parsed = urllib.parse.urlparse(image_url)
                                path_parts = parsed.path.split("/")
                                last_component = path_parts[-1]
                                image_id = os.path.splitext(last_component)[0]
                                image_filename = f"{chapter}_{image_id}.jpg"
                                target_dir = thumbnails_dir
                                target_dir.mkdir(parents=True, exist_ok=True)
                                target_path = target_dir / image_filename
                                req = urllib.request.Request(
                                    image_url,
                                    headers={"User-Agent": "Mozilla/5.0"}
                                )
                                with urllib.request.urlopen(req) as response, open(target_path, "wb") as out_file:
                                    out_file.write(response.read())
                                print(f"Downloaded thumbnail for {card_identifier} as {image_filename}")
                            except Exception as e:
                                print(f"Error downloading thumbnail for {card_identifier} from {image_url}: {e}")
                        
                        # Download high resolution image (2048) in den Ordner ThumbnailsHighRes
                        image_url_high = ""
                        if isinstance(image_urls, list):
                            for entry in image_urls:
                                if isinstance(entry, dict) and entry.get("height") == 2048:
                                    image_url_high = entry.get("url", "")
                                    break
                        elif isinstance(image_urls, dict):
                            for key, entry in image_urls.items():
                                if isinstance(entry, dict) and entry.get("height") == 2048:
                                    image_url_high = entry.get("url", "")
                                    break
                        high_res_dir = pathlib.Path(__file__).parent / "ThumbnailsHighRes"
                        if len(parts) > 1 and parts[1] and not parts[1][0].isdigit():
                            print(f"Skipping high res download for {card_identifier} due to letter in identifier.")
                        elif language == "en" and image_url_high:
                            try:
                                chapter = extract_chapter(card_identifier)
                                if not chapter.isdigit():
                                    chapter = "0"
                                parsed = urllib.parse.urlparse(image_url_high)
                                path_parts = parsed.path.split("/")
                                last_component = path_parts[-1]
                                image_id = os.path.splitext(last_component)[0]
                                image_filename = f"{chapter}_{image_id}.jpg"
                                high_res_dir.mkdir(parents=True, exist_ok=True)
                                target_path = high_res_dir / image_filename
                                req = urllib.request.Request(
                                    image_url_high,
                                    headers={"User-Agent": "Mozilla/5.0"}
                                )
                                with urllib.request.urlopen(req) as response, open(target_path, "wb") as out_file:
                                    out_file.write(response.read())
                                print(f"Downloaded high res image for {card_identifier} as {image_filename}")
                            except Exception as e:
                                print(f"Error downloading high res image for {card_identifier} from {image_url_high}: {e}")
    conn.close()

def main():
    download_catalog()
    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    thumbnails_dir = pathlib.Path(__file__).parent / "Thumbnails"
    # Datenbank unter dem neuen Namen erstellen
    db_path = pathlib.Path(__file__).parent / "cards_database_original_Scheme.sqlite"
    process_catalog_and_update_db(catalog_dir, thumbnails_dir, db_path)

if __name__ == "__main__":
    main()
