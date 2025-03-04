import codecs
import json
import os
import pathlib
import sqlite3
import urllib.request
import urllib.parse
import ssl

# --- Bestehende Funktionalität: Katalog downloaden ---
def card_filename(card):
    parts = card["card_identifier"].replace("/", "_").split(" ")
    parts.reverse()
    return f"{'-'.join(parts)}.json"

def download_catalog():
    # Authentifizierung holen
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

    # Hier wird der SSL-Context verwendet, der die Zertifikate überprüft (da du nun die Zertifikate installiert hast)
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

        # Iteriere über alle Kartentypen (z. B. actions, characters, etc.)
        for card_type in contents["cards"]:
            card_type_dir = cards_dir / card_type
            card_type_dir.mkdir(exist_ok=True)
            for card in contents["cards"][card_type]:
                if "abilities" in card:
                    card["abilities"].sort()
                with (card_type_dir / card_filename(card)).open("w", encoding="utf-8") as out:
                    json.dump(card, out, indent=2, ensure_ascii=False)

        # Speichere zusätzlich den restlichen Katalog (ohne Karten)
        del contents["cards"]
        with (lang_dir / "catalog-no-cards.json").open("w", encoding="utf-8") as out:
            json.dump(contents, out, indent=2, ensure_ascii=False)

# --- Neue Funktionalität: Datenbank-Update und Bilder-Download ---
def process_catalog_and_update_db(catalog_dir, images_root, db_path):
    # Verbinde zur SQLite-Datenbank (wird angelegt, falls noch nicht vorhanden)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Erstelle Tabelle, falls sie noch nicht existiert
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
    
    # Durchlaufe alle Sprachordner im katalog-Verzeichnis
    for lang_dir in catalog_dir.iterdir():
        if lang_dir.is_dir():
            language = lang_dir.name
            cards_dir = lang_dir / "cards"
            if cards_dir.exists():
                for category_dir in cards_dir.iterdir():
                    # Nur die Unterordner actions, characters, items und locations berücksichtigen
                    if category_dir.is_dir() and category_dir.name in {"actions", "characters", "items", "locations"}:
                        category = category_dir.name
                        for json_file in category_dir.glob("*.json"):
                            try:
                                with json_file.open("r", encoding="utf-8") as f:
                                    card = json.load(f)
                            except Exception as e:
                                print(f"Error reading {json_file}: {e}")
                                continue
                            
                            # Extrahiere die gewünschten Felder
                            name = card.get("name", "")
                            subtitle = card.get("subtitle", "")
                            sort_number = card.get("sort_number", 0)
                            rules_text = card.get("rules_text", "")
                            card_identifier = card.get("card_identifier", "")
                            # card_sets und magic_ink_colors werden als JSON-Strings gespeichert
                            card_sets = json.dumps(card.get("card_sets", ""))
                            magic_ink_colors = json.dumps(card.get("magic_ink_colors", ""))
                            
                            # Ermittle die URLs für die Bildauflösungen 2048 und 512
                            image_url_2048 = ""
                            image_url_512 = ""
                            if "image_urls" in card:
                                # Falls image_urls als Liste vorliegt:
                                if isinstance(card["image_urls"], list):
                                    for entry in card["image_urls"]:
                                        if isinstance(entry, dict) and "height" in entry and "url" in entry:
                                            if entry["height"] == 2048:
                                                image_url_2048 = entry["url"]
                                            elif entry["height"] == 512:
                                                image_url_512 = entry["url"]
                                # Alternativ, falls image_urls als Dictionary vorliegt:
                                elif isinstance(card["image_urls"], dict):
                                    for key, entry in card["image_urls"].items():
                                        if isinstance(entry, dict) and "height" in entry and "url" in entry:
                                            if entry["height"] == 2048:
                                                image_url_2048 = entry["url"]
                                            elif entry["height"] == 512:
                                                image_url_512 = entry["url"]

                            # Datensatz in die Datenbank einfügen
                            cursor.execute('''
                                INSERT INTO cards (
                                    language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                    image_url_2048, image_url_512, card_sets, magic_ink_colors
                                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                            ''', (language, category, name, subtitle, sort_number, rules_text, card_identifier,
                                  image_url_2048, image_url_512, card_sets, magic_ink_colors))
                            conn.commit()
                            
                            # --- Bilder herunterladen ---
                            def sanitize_identifier(identifier):
                                return identifier.replace(" ", "_").replace("/", "_")
                            
                            sanitized_identifier = sanitize_identifier(card_identifier)
                            
                            # Für jede Auflösung das Bild herunterladen
                            for res, url in [(2048, image_url_2048), (512, image_url_512)]:
                                if url:
                                    # Zielordner: Images/{language}/{resolution}/
                                    target_dir = images_root / language / str(res)
                                    target_dir.mkdir(parents=True, exist_ok=True)
                                    # Versuche, die Dateiendung aus der URL zu ermitteln, ansonsten .jpg
                                    ext = os.path.splitext(url)[1]
                                    if not ext:
                                        ext = ".jpg"
                                    target_path = target_dir / f"{sanitized_identifier}{ext}"
                                    try:
                                        urllib.request.urlretrieve(url, target_path)
                                        print(f"Downloaded image for {card_identifier} at resolution {res}")
                                    except Exception as e:
                                        print(f"Error downloading image for {card_identifier} from {url}: {e}")
    
    conn.close()

# --- Hauptfunktion, die beide Prozesse (Download und Processing) kombiniert ---
def main():
    # 1. Katalog herunterladen
    download_catalog()
    
    # 2. Anschließend die JSONs verarbeiten, in die Datenbank schreiben und die Bilder herunterladen
    catalog_dir = pathlib.Path(__file__).parent / "catalog"
    images_root = pathlib.Path(__file__).parent / "Images"
    db_path = pathlib.Path(__file__).parent / "cards.db"
    process_catalog_and_update_db(catalog_dir, images_root, db_path)
    
if __name__ == "__main__":
    main()
