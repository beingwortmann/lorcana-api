import codecs
import json
import os
import pathlib
import sqlite3
import urllib.request
import urllib.parse
import ssl

# Ermittelt den Dateinamen für eine Karte anhand ihres "card_identifier"
def card_filename(card):
    parts = card["card_identifier"].replace("/", "_").split(" ")
    parts.reverse()
    return f"{'-'.join(parts)}.json"

# Lädt den gesamten Katalog herunter und speichert ihn in einer strukturierten Ordnerhierarchie
def download_catalog():
    token_auth = codecs.decode(
        (
            b"42617369632062473979593246755953316863476b74636d56685a447046646b4a724d7a4a6"
            b"b5157746b4d7a6c756457743551564e494d4863325832464a63565a456348704a656e567253"
            b"306c7863446c424e58526c6232633552334a6b51314a484d55464261445653656e644d64455"
            b"26b596c527063326b3354484a5957446c325930466b535449345330393664773d3d"
        ),
        "hex",
    ).decode()
    token_request = urllib.request.Request(
        "https://sso.ravensburger.de/token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={"Authorization": token_auth, "User-Agent": ""},
    )

    # Zertifikatsüberprüfung funktioniert jetzt, da die entsprechenden Zertifikate installiert sind.
    with urllib.request.urlopen(token_request) as f:
        token = json.loads(f.read().decode("utf-8"))

    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    catalog_dir.mkdir(exist_ok=True)

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

        # Durchlaufen aller Kartentypen
        for card_type in contents["cards"]:
            card_type_dir = cards_dir / card_type
            card_type_dir.mkdir(exist_ok=True)
            for card in contents["cards"][card_type]:
                if "abilities" in card:
                    card["abilities"].sort()
                with (card_type_dir / card_filename(card)).open("w", encoding="utf-8") as out:
                    json.dump(card, out, indent=2, ensure_ascii=False)

        # Speichert zusätzlich den restlichen Katalog (ohne Karten)
        del contents["cards"]
        with (lang_dir / "catalog-no-cards.json").open("w", encoding="utf-8") as out:
            json.dump(contents, out, indent=2, ensure_ascii=False)

# Verarbeitet die heruntergeladenen JSON-Dateien, aktualisiert die SQLite-Datenbank
# und lädt die Bilder in der gewünschten Ordnerstruktur herunter.
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
        magic_ink_colors TEXT
    )
    ''')
    conn.commit()
    
    for lang_dir in catalog_dir.iterdir():
        if lang_dir.is_dir():
            language = lang_dir.name
            cards_dir = lang_dir / "cards"
            if cards_dir.exists():
                for category_dir in cards_dir.iterdir():
                    # Nur Unterordner actions, characters, items und locations berücksichtigen
                    if category_dir.is_dir() and category_dir.name in {"actions", "characters", "items", "locations"}:
                        category = category_dir.name
                        for json_file in category_dir.glob("*.json"):
                            try:
                                with json_file.open("r", encoding="utf-8") as f:
                                    card = json.load(f)
                            except Exception as e:
                                print(f"Error reading {json_file}: {e}")
                                continue
                            
                            # Extrahiere die gewünschten Felder aus der Karte
                            name = card.get("name", "")
                            subtitle = card.get("subtitle", "")
                            sort_number = card.get("sort_number", 0)
                            rules_text = card.get("rules_text", "")
                            card_identifier = card.get("card_identifier", "")
                            card_sets = json.dumps(card.get("card_sets", ""))
                            magic_ink_colors = json.dumps(card.get("magic_ink_colors", ""))
                            
                            # Ermittle die Bild-URLs für die Auflösungen 2048 und 512
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

                            # Füge den Datensatz in die SQLite-Datenbank ein
                            cursor.execute('''
                                INSERT INTO cards (
                                    language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                    image_url_2048, image_url_512, card_sets, magic_ink_colors
                                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                            ''', (language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                  image_url_2048, image_url_512, card_sets, magic_ink_colors))
                            conn.commit()
                            
                            # Funktion zum Bereinigen des card_identifier (Leerzeichen und Schrägstriche ersetzen)
                            def sanitize_identifier(identifier):
                                return identifier.replace(" ", "_").replace("/", "_")
                            
                            sanitized_identifier = sanitize_identifier(card_identifier)
                            
                            # Für jede Auflösung das Bild herunterladen, diesmal mit einem benutzerdefinierten User-Agent
                            for res, url in [(2048, image_url_2048), (512, image_url_512)]:
                                if url:
                                    target_dir = images_root / language / str(res)
                                    target_dir.mkdir(parents=True, exist_ok=True)
                                    ext = os.path.splitext(url)[1]
                                    if not ext:
                                        ext = ".jpg"
                                    target_path = target_dir / f"{sanitized_identifier}{ext}"
                                    
                                    # Erstelle einen Request mit einem modernen User-Agent (optional Referer hinzufügen)
                                    req = urllib.request.Request(
                                        url,
                                        headers={
                                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
                                            # "Referer": "https://lorcana.ravensburger.com/"
                                        }
                                    )
                                    try:
                                        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
                                            out_file.write(response.read())
                                        print(f"Downloaded image for {card_identifier} at resolution {res}")
                                    except Exception as e:
                                        print(f"Error downloading image for {card_identifier} from {url}: {e}")
    
    conn.close()

# Hauptfunktion: Führt den Download des Katalogs und anschließende Verarbeitung (DB-Update und Bilder-Download) aus.
def main():
    download_catalog()
    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    images_root = pathlib.Path(__file__).parent / "Images"
    db_path = pathlib.Path(__file__).parent / "cards.db"
    process_catalog_and_update_db(catalog_dir, images_root, db_path)
    
if __name__ == "__main__":
    main()
