#!/usr/bin/env python3
import csv
import json
import os
import requests
import shutil
import sqlite3
from io import StringIO

# --- Step 1: Load Groups (from JSON) ---
groups_url = "https://tcgcsv.com/tcgplayer/71/groups"
response = requests.get(groups_url)
if response.status_code != 200:
    print(f"Error loading groups from {groups_url}: {response.status_code}")
    exit(1)

groups_data = response.json()
if isinstance(groups_data, dict) and "results" in groups_data:
    groups_list = groups_data["results"]
elif isinstance(groups_data, list):
    groups_list = groups_data
else:
    print("Unexpected format for groups data. Expected a list or a dict with a 'results' key.")
    exit(1)

groups = {}
for group in groups_list:
    if "groupId" in group and "abbreviation" in group:
        group_id = group["groupId"]
        # Derive chapter from publishedOn (first 4 characters) or default to "0"
        chapter = group.get("publishedOn", "0")[:4]
        abbreviation = group["abbreviation"]
        groups[group_id] = {"chapter": chapter, "abbreviation": abbreviation}
    else:
        print("Skipping group with missing fields:", group)

print("Loaded groups:", groups)

# --- Step 2: Download CSV for each Group and process rows ---
all_rows = []
for group_id, info in groups.items():
    csv_url = f"https://tcgcsv.com/tcgplayer/71/{group_id}/ProductsAndPrices.csv"
    print(f"Downloading CSV for group {group_id} from {csv_url}")
    csv_response = requests.get(csv_url)
    if csv_response.status_code != 200:
        print(f"Error loading CSV for group {group_id}: {csv_response.status_code}")
        continue
    csv_text = csv_response.text
    reader = csv.DictReader(StringIO(csv_text))
    count = 0
    for row in reader:
        count += 1
        extNumber = row.get("extNumber", "").strip()
        # Generate card_identifier using the extNumber, literal "EN", and abbreviation.
        generated_identifier = f"{extNumber} EN {info['abbreviation']}"
        row["card_identifier"] = generated_identifier
        row["chapter"] = info["chapter"]
        all_rows.append(row)
    print(f"Group {group_id} provided {count} rows.")

# --- Step 3: Merge all CSV rows into one file ---
merged_csv_path = "merged_products_and_prices.csv"
if not all_rows:
    print("No CSV rows to merge! Please check the groups and CSV endpoints.")
    exit(1)

# Compute the union of all keys across all rows
all_fieldnames = set()
for row in all_rows:
    all_fieldnames.update(row.keys())
fieldnames = sorted(all_fieldnames)

with open(merged_csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in all_rows:
        writer.writerow(row)

print(f"Merged CSV file written to {merged_csv_path} with {len(all_rows)} rows.")

# --- Step 4: Update SQLite DB ---
if not os.path.exists("cards.db"):
    print("cards.db not found!")
    exit(1)
shutil.copy("cards.db", "cardsWithPrices.db")
conn = sqlite3.connect("cardsWithPrices.db")
cursor = conn.cursor()

# Add new columns if they don't exist.
for col in ["lowPrice", "midPrice", "marketPrice"]:
    try:
        cursor.execute(f"ALTER TABLE cards ADD COLUMN {col} TEXT")
        conn.commit()
        print(f"Added column {col}")
    except sqlite3.OperationalError as e:
        print(f"Column {col} may already exist: {e}")

# Build a mapping from normalized card_identifier to DB id.
# Normalization: from the DB card_identifier, split by whitespace and use first and last tokens.
db_mapping = {}
cursor.execute("SELECT id, card_identifier FROM cards")
for row in cursor.fetchall():
    db_id, db_card_identifier = row
    if db_card_identifier:
        parts = db_card_identifier.split()
        if len(parts) >= 3:
            normalized = f"{parts[0]}|{parts[-1]}"
            db_mapping[normalized] = db_id

print("DB mapping (normalized card_identifier):", db_mapping)

update_count = 0
unmatched_count = 0

with open(merged_csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row.get("subTypeName", "") != "Normal":
            continue
        csv_card_identifier = row["card_identifier"]
        parts = csv_card_identifier.split()
        if len(parts) < 3:
            continue
        normalized_csv = f"{parts[0]}|{parts[-1]}"
        if normalized_csv in db_mapping:
            card_db_id = db_mapping[normalized_csv]
            lowPrice = row.get("lowPrice", None)
            midPrice = row.get("midPrice", None)
            marketPrice = row.get("marketPrice", None)
            cursor.execute("""
            UPDATE cards
            SET lowPrice = ?, midPrice = ?, marketPrice = ?
            WHERE id = ?
            """, (lowPrice, midPrice, marketPrice, card_db_id))
            conn.commit()
            update_count += 1
        else:
            if unmatched_count < 5:
                print(f"No match found in DB for normalized card_identifier: {normalized_csv}")
            unmatched_count += 1

conn.close()
print(f"Updated {update_count} rows in cardsWithPrices.db successfully.")
if unmatched_count > 0:
    print(f"{unmatched_count} rows did not match any DB record. Please verify your matching logic.")
