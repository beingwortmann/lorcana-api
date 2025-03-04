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

# Parse the JSON response. Expecting a dict with a "results" key.
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
    # Expect each group to have keys: groupId and abbreviation.
    # We derive 'chapter' from the publishedOn field's year (if available) or default to "0".
    if "groupId" in group and "abbreviation" in group:
        group_id = group["groupId"]
        chapter = group.get("publishedOn", "0")[:4]  # Extract year as chapter
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
        # Process extNumber: replace any slash with an underscore
        extNumber = row.get("extNumber", "")
        extNumber_processed = extNumber.replace("/", "_")
        # Generate cardId as: {chapter}{abbreviation}-EN-{extNumber_processed}
        cardId = f"{info['chapter']}{info['abbreviation']}-EN-{extNumber_processed}"
        row["cardId"] = cardId
        row["chapter"] = info["chapter"]
        all_rows.append(row)
    print(f"Group {group_id} provided {count} rows.")

# --- Step 3: Merge all CSV rows into one file ---
merged_csv_path = "merged_products_and_prices.csv"
if not all_rows:
    print("No CSV rows to merge! Please check the groups and CSV endpoints.")
    exit(1)

# Compute the union of all keys across all rows to account for extra fields
all_fieldnames = set()
for row in all_rows:
    all_fieldnames.update(row.keys())
fieldnames = sorted(all_fieldnames)  # sorting for consistency

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

with open(merged_csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    update_count = 0
    for row in reader:
        # Only process rows where subTypeName is "Normal"
        if row.get("subTypeName", "") != "Normal":
            continue
        cardId = row["cardId"]
        lowPrice = row.get("lowPrice", None)
        midPrice = row.get("midPrice", None)
        marketPrice = row.get("marketPrice", None)
        # Match using cardId by normalizing language markers in card_identifier
        query = """
        SELECT id FROM cards 
        WHERE REPLACE(REPLACE(REPLACE(card_identifier, '-DE-', '-EN-'), '-FR-', '-EN-'), '-IT-', '-EN-') = ?
        """
        cursor.execute(query, (cardId,))
        result = cursor.fetchone()
        if result:
            card_db_id = result[0]
            cursor.execute("""
            UPDATE cards
            SET lowPrice = ?, midPrice = ?, marketPrice = ?
            WHERE id = ?
            """, (lowPrice, midPrice, marketPrice, card_db_id))
            conn.commit()
            update_count += 1

conn.close()
print(f"Updated {update_count} rows in cardsWithPrices.db successfully.")
