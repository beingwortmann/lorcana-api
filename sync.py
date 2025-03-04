import codecs
import json
import os
import pathlib
import sqlite3
import urllib.request
import urllib.parse
import ssl

def card_filename(card):
    parts = card["card_identifier"].replace("/", "_").split(" ")
    parts.reverse()
    return f"{'-'.join(parts)}.json"

def download_catalog():
    token_auth = codecs.decode(os.environ['LORCANA_SECRET_TOKEN'].strip(), 'hex').decode()
    token_request = urllib.request.Request(
        "https://sso.ravensburger.de/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": token_auth, "User-Agent": ""},
    )

    with urllib.request.urlopen(token_request) as f:
        token = json.loads(f.read().decode("utf-8"))

    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    catalog_dir.mkdir(exist_ok=True)

    # Lade alle Sprachkataloge (de, en, fr, it)
    for lang in ("de", "en", "fr", "it"):
        print(f"Downloading {lang} catalog")
        catalog_auth = f"{token['token_type']} {token['access_token']}"
        catalog_request = urllib.request.Request(
            f"https://api.lorcana.ravensburger.com/v2/catalog/{lang}",
            headers={"Authorization": catalog_auth, "User-Agent": ""},
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
                with (card_type_dir / card_filename(card)).open("w", encoding="utf-8") as out:
                    json.dump(card, out, indent=2, ensure_ascii=False)

        del contents["cards"]
        with (lang_dir / "catalog-no-cards.json").open("w", encoding="utf-8") as out:
            json.dump(contents, out, indent=2, ensure_ascii=False)

def extract_language_from_url(url):
    """
    Extrahiert den Sprachcode aus einer URL, z.B. aus
    "https://api.lorcana.ravensburger.com/images/en/..."
    wird "en" zurückgegeben.
    """
    parsed = urllib.parse.urlparse(url)
    parts = parsed.path.split("/")
    if len(parts) > 2:
        return parts[2]
    return None

def process_catalog_and_update_db(catalog_dir, images_root, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        language TEXT,
        category TEXT,
        name TEXT,
        subtitle TEXT,
        sort_number INTEGER,
        rules_text TEXT,
        card_identifier TEXT,
        image_url_2048 TEXT,
        image_url_512 TEXT,
        card_sets TEXT,
        magic_ink_colors TEXT,
        foil_mask_url TEXT,
        flavor_text TEXT,
        ink_cost TEXT,
        ink_convertible TEXT
    )
    ''')
    conn.commit()
    
    # Durchlaufe alle Sprachordner im Katalog
    for lang_dir in catalog_dir.iterdir():
        if lang_dir.is_dir():
            folder_language = lang_dir.name  # Fallback, falls keine URL-Sprachinfo gefunden wird.
            print(f"Processing folder: {folder_language}")
            cards_dir = lang_dir / "cards"
            if cards_dir.exists():
                for category_dir in cards_dir.iterdir():
                    if category_dir.is_dir() and category_dir.name in {"actions", "characters", "items", "locations"}:
                        category = category_dir.name
                        for json_file in category_dir.glob("*.json"):
                            try:
                                with json_file.open("r", encoding="utf-8") as f:
                                    card = json.load(f)
                            except Exception as e:
                                print(f"Error reading {json_file}: {e}")
                                continue
                            
                            # Extrahiere die Felder
                            name = card.get("name", "")
                            subtitle = card.get("subtitle", "")
                            sort_number = card.get("sort_number", 0)
                            rules_text = card.get("rules_text", "")
                            card_identifier = card.get("card_identifier", "")
                            card_sets = json.dumps(card.get("card_sets", ""))
                            magic_ink_colors = json.dumps(card.get("magic_ink_colors", ""))
                            foil_mask_url = card.get("foil_mask_url", "")
                            flavor_text = card.get("flavor_text", "")
                            ink_cost = card.get("ink_cost", "")
                            ink_convertible = card.get("ink_convertible", "")
                            
                            image_url_2048 = ""
                            image_url_512 = ""
                            if "image_urls" in card:
                                if isinstance(card["image_urls"], list):
                                    for entry in card["image_urls"]:
                                        if isinstance(entry, dict) and "height" in entry and "url" in entry:
                                            if entry["height"] == 2048:
                                                image_url_2048 = entry["url"]
                                            elif entry["height"] == 512:
                                                image_url_512 = entry["url"]
                                elif isinstance(card["image_urls"], dict):
                                    for key, entry in card["image_urls"].items():
                                        if isinstance(entry, dict) and "height" in entry and "url" in entry:
                                            if entry["height"] == 2048:
                                                image_url_2048 = entry["url"]
                                            elif entry["height"] == 512:
                                                image_url_512 = entry["url"]

                            # Ermitteln der Sprache anhand der URLs (falls vorhanden)
                            detected_language = None
                            for candidate in [image_url_2048, image_url_512, foil_mask_url]:
                                if candidate:
                                    detected_language = extract_language_from_url(candidate)
                                    if detected_language:
                                        break
                            if not detected_language:
                                detected_language = folder_language

                            # Datensatz in die DB einfügen – hier wird der ermittelte Sprachcode genutzt
                            cursor.execute('''
                                INSERT INTO cards (
                                    language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                    image_url_2048, image_url_512, card_sets, magic_ink_colors, foil_mask_url, flavor_text, ink_cost, ink_convertible
                                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                            ''', (detected_language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                  image_url_2048, image_url_512, card_sets, magic_ink_colors, foil_mask_url, flavor_text, ink_cost, ink_convertible))
                            conn.commit()
                            
                            def sanitize_identifier(identifier):
                                return identifier.replace(" ", "_").replace("/", "_")
                            
                            sanitized_identifier = sanitize_identifier(card_identifier)
                            
                            # Herunterladen der Bilder für 2048 und 512 – Zielordner anhand der ermittelten Sprache
                            for res, url in [(2048, image_url_2048), (512, image_url_512)]:
                                if url:
                                    target_dir = images_root / detected_language / str(res)
                                    target_dir.mkdir(parents=True, exist_ok=True)
                                    
                                    parsed_url = urllib.parse.urlparse(url)
                                    ext = os.path.splitext(parsed_url.path)[1]
                                    
                                    target_path = target_dir / f"{sanitized_identifier}{ext}"
                                    
                                    req = urllib.request.Request(
                                        url,
                                        headers={
                                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                                        }
                                    )
                                    try:
                                        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
                                            out_file.write(response.read())
                                        print(f"Downloaded image for {card_identifier} at resolution {res} in {detected_language}")
                                    except Exception as e:
                                        print(f"Error downloading image for {card_identifier} from {url}: {e}")
                            
                            # Herunterladen des foil_mask-Bildes (falls vorhanden)
                            if foil_mask_url:
                                target_dir = images_root / detected_language / "foil_mask"
                                target_dir.mkdir(parents=True, exist_ok=True)
                                
                                parsed_url = urllib.parse.urlparse(foil_mask_url)
                                ext = os.path.splitext(parsed_url.path)[1]
                                
                                target_path = target_dir / f"{sanitized_identifier}{ext}"
                                
                                req = urllib.request.Request(
                                    foil_mask_url,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                                    }
                                )
                                try:
                                    with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
                                        out_file.write(response.read())
                                    print(f"Downloaded foil mask for {card_identifier} in {detected_language}")
                                except Exception as e:
                                    print(f"Error downloading foil mask for {card_identifier} from {foil_mask_url}: {e}")
    
    conn.close()

def main():
    download_catalog()
    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    images_root = pathlib.Path(__file__).parent / "Images"
    db_path = pathlib.Path(__file__).parent / "cards.db"
    process_catalog_and_update_db(catalog_dir, images_root, db_path)
    
if __name__ == "__main__":
    main()
