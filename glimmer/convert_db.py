#!/usr/bin/env python3
import sqlite3
import pathlib

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
    
    count = 0
    english_cards_data = []
    other_language_cards_data = []

    for row in rows:
        if " EN " in row["card_identifier"]:
            english_cards_data.append(row)
        else:
            other_language_cards_data.append(row)

    english_image_urls_by_deck_id = {}

    # Process English cards first
    for row in english_cards_data:
        # Mapping der neuen Spalten zu den alten:
        # Neue -> Alte
        # magic_ink_colors      -> color
        # ink_convertible       -> inkwell (als Boolean, hier 1 für True, sonst 0)
        # rarity                -> rarity
        # type                  -> type
        # card_identifier       -> fullIdentifier
        # card_sets             -> setNumber (als Integer, versuche zu konvertieren, sonst 0)
        # number                -> number
        # author                -> artist
        # name                  -> baseName
        # fullName              -> fullName
        # name                  -> simpleName
        # subtitle              -> subtitle
        # ink_cost              -> cost (als Integer, falls möglich, sonst 0)
        # quest_value           -> lore (als Integer, falls möglich, sonst 0)
        # strength              -> strength (als Integer, falls möglich, sonst 0)
        # willpower             -> willpower (als Integer, falls möglich, sonst 0)
        # flavor_text           -> flavorText
        # rules_text            -> fullText
        # story                 -> (nicht verwendet, daher NULL)
        # image_url             -> imageUrl
        
        color = row["magic_ink_colors"]
        inkwell = 1 if row["ink_convertible"] == 1 else 0
        rarity = row["rarity"]
        type_field = row["type"]
        fullIdentifier = row["card_identifier"]
        try:
            setNumber = int(row["card_sets"])
        except Exception:
            setNumber = 0
        number = row["number"]
        artist = row["author"]
        baseName = row["name"]
        fullName = row["fullName"]
        simpleName = row["name"]
        subtitle = row["subtitle"]
        try:
            cost = int(row["ink_cost"])
        except Exception:
            cost = 0
        try:
            lore = int(row["quest_value"])
        except Exception:
            lore = 0
        try:
            strength = int(row["strength"])
        except Exception:
            strength = 0
        try:
            willpower = int(row["willpower"])
        except Exception:
            willpower = 0
        flavorText = row["flavor_text"]
        fullText = row["rules_text"]
        story = None
        imageUrl = row["image_url"]
        deck_building_id = row["deck_building_id"]

        if deck_building_id and imageUrl:
            english_image_urls_by_deck_id[deck_building_id] = imageUrl
        
        tgt_cursor.execute(insert_query, (
            color, inkwell, rarity, type_field, fullIdentifier, setNumber, number,
            artist, baseName, fullName, simpleName, subtitle, cost, lore, strength,
            willpower, flavorText, fullText, story, imageUrl, deck_building_id
        ))
        count += 1

    # Process other language cards
    for row in other_language_cards_data:
        color = row["magic_ink_colors"]
        inkwell = 1 if row["ink_convertible"] == 1 else 0
        rarity = row["rarity"]
        type_field = row["type"]
        fullIdentifier = row["card_identifier"]
        try:
            setNumber = int(row["card_sets"])
        except Exception:
            setNumber = 0
        number = row["number"]
        artist = row["author"]
        baseName = row["name"]
        fullName = row["fullName"]
        simpleName = row["name"]
        subtitle = row["subtitle"]
        try:
            cost = int(row["ink_cost"])
        except Exception:
            cost = 0
        try:
            lore = int(row["quest_value"])
        except Exception:
            lore = 0
        try:
            strength = int(row["strength"])
        except Exception:
            strength = 0
        try:
            willpower = int(row["willpower"])
        except Exception:
            willpower = 0
        flavorText = row["flavor_text"]
        fullText = row["rules_text"]
        story = None
        
        deck_building_id = row["deck_building_id"]
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
    convert_database(new_db, old_schema_db)
