#!/usr/bin/env python3
import sqlite3
import pathlib
import re

def convert_database(new_db_path, old_schema_db_path):
    # Verbindung zur Quell-Datenbank (neues Schema) herstellen
    src_conn = sqlite3.connect(new_db_path)
    src_conn.row_factory = sqlite3.Row
    src_cursor = src_conn.cursor()
    
    # Ziel-Datenbank erstellen/öffnen (altes Schema)
    tgt_conn = sqlite3.connect(old_schema_db_path)
    tgt_cursor = tgt_conn.cursor()
    
    # Alte Tabelle (mit den alten Bezeichnungen) anlegen:
    tgt_cursor.execute('''
    CREATE TABLE IF NOT EXISTS cards (
        id INTEGER PRIMARY KEY,
        color TEXT,
        inkwell BOOLEAN,
        rarity TEXT,
        type TEXT,
        fullIdentifier TEXT,
        setNumber INTEGER,
        number INTEGER,
        artist TEXT,
        baseName TEXT,
        fullName TEXT,
        simpleName TEXT,
        subtitle TEXT,
        cost INTEGER,
        lore INTEGER,
        strength INTEGER,
        willpower INTEGER,
        flavorText TEXT,
        fullText TEXT,
        story TEXT,
        imageUrl TEXT,
        deck_building_id TEXT
    )
    ''')
    # Bestehende Daten löschen, um Duplikate bei wiederholtem Ausführen zu vermeiden
    tgt_cursor.execute('DELETE FROM cards')
    tgt_conn.commit()
    
    # Alle Zeilen aus der neuen Tabelle (neues Schema) lesen
    src_cursor.execute("SELECT * FROM cards")
    rows = src_cursor.fetchall()
    print(f"Found {len(rows)} rows in the new schema database.")
    
    # Einfüge-Query für das alte Schema
    insert_query = '''
    INSERT INTO cards (
        color, inkwell, rarity, type, fullIdentifier, setNumber, number,
        artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
        willpower, flavorText, fullText, story, imageUrl, deck_building_id
    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    '''
    
    # --- NEUE LOGIK: Karten vorsortieren ---
    
    # Hilfsfunktion, um zu prüfen, ob es sich um eine normale Version handelt
    def is_normal_version(identifier):
        if not identifier:
            return False
        parts = identifier.split('/')
        if len(parts) > 1:
            # z.B. "204 EN 5" oder "P2 EN 5" -> extrahiert "204" oder "P2"
            potential_set_total_token = parts[1].split(' ')[0]
            return potential_set_total_token.isdigit()
        return False

    # Hilfsfunktion, um den Sprachcode zu extrahieren (z.B. "DE" aus "1/204 DE 5")
    def get_lang_code(identifier):
        if not identifier:
            return None
        # Sucht nach einem zweibuchstabigen Code, umgeben von Leerzeichen
        match = re.search(r'\s([A-Z]{2})\s', identifier)
        return match.group(1) if match else None

    normal_english_cards = []
    special_english_cards = []
    normal_other_lang_cards = []
    special_other_lang_cards = []

    for row in rows:
        identifier = row["card_identifier"]
        is_normal = is_normal_version(identifier)
        
        if " EN " in identifier:
            if is_normal:
                normal_english_cards.append(row)
            else:
                special_english_cards.append(row)
        else:
            if is_normal:
                normal_other_lang_cards.append(row)
            else:
                special_other_lang_cards.append(row)

    print(f"Sorted cards: {len(normal_english_cards)} normal EN, {len(special_english_cards)} special EN, "
          f"{len(normal_other_lang_cards)} normal other, {len(special_other_lang_cards)} special other.")

    # --- Verarbeitung der Karten in der neuen Reihenfolge ---
    
    count = 0
    english_image_urls_by_deck_id = {}
    processed_english_deck_ids = set()
    processed_other_lang_cards = {}  # Format: {'DE': {id1, id2}, 'FR': {id3}}

    # 1. Normale englische Karten verarbeiten
    for row in normal_english_cards:
        # Mapping der Spalten (wie im Originalcode)
        color, inkwell, rarity, type_field, fullIdentifier, setNumber, number, artist, baseName, fullName, simpleName, subtitle, cost, lore, strength, willpower, flavorText, fullText, story, deck_building_id = (
            row["magic_ink_colors"], 1 if row["ink_convertible"] == 1 else 0, row["rarity"], row["type"], row["card_identifier"],
            int(row["card_sets"]) if row["card_sets"] and row["card_sets"].isdigit() else 0, row["number"], row["author"], row["name"],
            row["fullName"], row["name"], row["subtitle"], int(row["ink_cost"]) if row["ink_cost"] else 0,
            int(row["quest_value"]) if row["quest_value"] else 0, int(row["strength"]) if row["strength"] else 0,
            int(row["willpower"]) if row["willpower"] else 0, row["flavor_text"], row["rules_text"], None, row["deck_building_id"]
        )
        imageUrl = row["image_url"]
        
        # Speichere die Bild-URL der normalen englischen Karte
        if deck_building_id and imageUrl:
            english_image_urls_by_deck_id[deck_building_id] = imageUrl
        
        tgt_cursor.execute(insert_query, (
            color, inkwell, rarity, type_field, fullIdentifier, setNumber, number,
            artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
            willpower, flavorText, fullText, story, imageUrl, deck_building_id
        ))
        processed_english_deck_ids.add(deck_building_id)
        count += 1
        
    # 2. Besondere englische Karten verarbeiten
    for row in special_english_cards:
        deck_building_id = row["deck_building_id"]
        if deck_building_id in processed_english_deck_ids:
            continue  # Überspringen, da eine normale Version bereits existiert

        color, inkwell, rarity, type_field, fullIdentifier, setNumber, number, artist, baseName, fullName, simpleName, subtitle, cost, lore, strength, willpower, flavorText, fullText, story, deck_building_id = (
            row["magic_ink_colors"], 1 if row["ink_convertible"] == 1 else 0, row["rarity"], row["type"], row["card_identifier"],
            int(row["card_sets"]) if row["card_sets"] and row["card_sets"].isdigit() else 0, row["number"], row["author"], row["name"],
            row["fullName"], row["name"], row["subtitle"], int(row["ink_cost"]) if row["ink_cost"] else 0,
            int(row["quest_value"]) if row["quest_value"] else 0, int(row["strength"]) if row["strength"] else 0,
            int(row["willpower"]) if row["willpower"] else 0, row["flavor_text"], row["rules_text"], None, row["deck_building_id"]
        )
        imageUrl = row["image_url"] # Besondere Karten behalten vorerst ihre eigene URL
        
        tgt_cursor.execute(insert_query, (
            color, inkwell, rarity, type_field, fullIdentifier, setNumber, number,
            artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
            willpower, flavorText, fullText, story, imageUrl, deck_building_id
        ))
        count += 1

    # 3. Normale Karten in anderen Sprachen verarbeiten
    for row in normal_other_lang_cards:
        color, inkwell, rarity, type_field, fullIdentifier, setNumber, number, artist, baseName, fullName, simpleName, subtitle, cost, lore, strength, willpower, flavorText, fullText, story, deck_building_id = (
            row["magic_ink_colors"], 1 if row["ink_convertible"] == 1 else 0, row["rarity"], row["type"], row["card_identifier"],
            int(row["card_sets"]) if row["card_sets"] and row["card_sets"].isdigit() else 0, row["number"], row["author"], row["name"],
            row["fullName"], row["name"], row["subtitle"], int(row["ink_cost"]) if row["ink_cost"] else 0,
            int(row["quest_value"]) if row["quest_value"] else 0, int(row["strength"]) if row["strength"] else 0,
            int(row["willpower"]) if row["willpower"] else 0, row["flavor_text"], row["rules_text"], None, row["deck_building_id"]
        )
        imageUrl = english_image_urls_by_deck_id.get(deck_building_id, row["image_url"])
        lang_code = get_lang_code(fullIdentifier)
        
        tgt_cursor.execute(insert_query, (
            color, inkwell, rarity, type_field, fullIdentifier, setNumber, number,
            artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
            willpower, flavorText, fullText, story, imageUrl, deck_building_id
        ))
        
        if lang_code and deck_building_id:
            if lang_code not in processed_other_lang_cards:
                processed_other_lang_cards[lang_code] = set()
            processed_other_lang_cards[lang_code].add(deck_building_id)
        count += 1

    # 4. Besondere Karten in anderen Sprachen verarbeiten
    for row in special_other_lang_cards:
        deck_building_id = row["deck_building_id"]
        fullIdentifier = row["card_identifier"]
        lang_code = get_lang_code(fullIdentifier)

        if lang_code and deck_building_id in processed_other_lang_cards.get(lang_code, set()):
            continue # Überspringen, da eine normale Version in dieser Sprache existiert

        color, inkwell, rarity, type_field, setNumber, number, artist, baseName, fullName, simpleName, subtitle, cost, lore, strength, willpower, flavorText, fullText, story = (
            row["magic_ink_colors"], 1 if row["ink_convertible"] == 1 else 0, row["rarity"], row["type"],
            int(row["card_sets"]) if row["card_sets"] and row["card_sets"].isdigit() else 0, row["number"], row["author"], row["name"],
            row["fullName"], row["name"], row["subtitle"], int(row["ink_cost"]) if row["ink_cost"] else 0,
            int(row["quest_value"]) if row["quest_value"] else 0, int(row["strength"]) if row["strength"] else 0,
            int(row["willpower"]) if row["willpower"] else 0, row["flavor_text"], row["rules_text"], None
        )
        imageUrl = english_image_urls_by_deck_id.get(deck_building_id, row["image_url"])
        
        tgt_cursor.execute(insert_query, (
            color, inkwell, rarity, type_field, fullIdentifier, setNumber, number,
            artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
            willpower, flavorText, fullText, story, imageUrl, deck_building_id
        ))
        count += 1

    tgt_conn.commit()
    print(f"Converted and inserted {count} rows into the old schema database.")
    
    src_conn.close()
    tgt_conn.close()

if __name__ == "__main__":
    base_dir = pathlib.Path(__file__).parent
    new_db = base_dir / "cards_database_original_Scheme.sqlite"
    old_schema_db = base_dir / "cards_database.sqlite"
    
    # Sicherstellen, dass die Zieldatenbank existiert, aber leer ist, bevor wir beginnen
    if old_schema_db.exists():
        old_schema_db.unlink()
        print(f"Removed existing target database: {old_schema_db}")
        
    convert_database(new_db, old_schema_db)