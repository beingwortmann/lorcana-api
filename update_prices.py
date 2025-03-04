#!/usr/bin/env python3
import csv
import requests
import sqlite3
import os
import shutil
from io import StringIO

# --- Step 1: Load Groups ---
groups_url = "https://tcgcsv.com/tcgplayer/71/groups"
response = requests.get(groups_url)
if response.status_code != 200:
    print("Error loading groups")
    exit(1)

groups = {}
reader = csv.DictReader(StringIO(response.text))
for row in reader:
    group_id = row['groupId']
    chapter = row['chapter']          # Assumes the CSV has a "chapter" column.
    abbreviation = row['abbreviation']  # Assumes the CSV has an "abbreviation" column.
    groups[group_id] = {'chapter': chapter, 'abbreviation': abbreviation}

# --- Step 2: Download CSV for each Group and add extra columns ---
all_rows = []
for group_id, info in groups.items():
    csv_url = f"https://tcgcsv.com/tcgplayer/71/{group_id}/ProductsAndPrices.csv"
    resp = requests.get(csv_url)
    if resp.status_code != 200:
        print(f"Error loading CSV for group {group_id}")
        continue
    reader = csv.DictReader(StringIO(resp.text))
    for row in reader:
        # Process extNumber: replace any slash with an underscore
        extNumber = row.get('extNumber', '')
        extNumber = extNumber.replace('/', '_')
        # Generate cardId as ChapterNumber(abbreviation)-EN-extNumber
        cardId = f"{info['chapter']}{info['abbreviation']}-EN-{extNumber}"
        row['cardId'] = cardId
        row['chapter'] = info['chapter']
        all_rows.append(row)

# --- Step 3: Merge all CSV rows into one file ---
merged_csv_path = "merged_products_and_prices.csv"
if not all_rows:
    print("No CSV rows to merge!")
    exit(1)
with open(merged_csv_path, 'w', newline='', encoding='utf-8') as f:
    fieldnames = list(all_rows[0].keys())
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in all_rows:
        writer.writerow(row)

# --- Step 4: Update SQLite DB ---
# Copy the existing cards.db to cardsWithPrices.db
if not os.path.exists("cards.db"):
    print("cards.db not found!")
    exit(1)
shutil.copy("cards.db", "cardsWithPrices.db")

conn = sqlite3.connect("cardsWithPrices.db")
cursor = conn.cursor()

with open(merged_csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Only process rows with subTypeName "Normal"
        if row.get('subTypeName', '') != "Normal":
            continue
        cardId = row['cardId']
        lowPrice = row.get('lowPrice', None)
        midPrice = row.get('midPrice', None)
        marketPrice = row.get('marketPrice', None)
        # Match using cardId by normalizing language markers:
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

conn.close()
print("cardsWithPrices.db updated successfully.")
