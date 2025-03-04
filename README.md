# Lorcana Card Data Downloader & Processor

![Last Commit](https://img.shields.io/github/last-commit/beingwortmann/lorcana-api?style=flat-square)
![Check for Updates](https://github.com/beingwortmann/lorcana-api/actions/workflows/check-for-changes.yml/badge.svg)
![Uses SQLite](https://img.shields.io/badge/SQLite-003B57?style=flat&logo=sqlite&logoColor=white)

---
### My Card Scanner/Inventory App on the Appstore (Glimmer Scan) will be using this soon. I am thankful for every possible support

[![Find my App using this on the Appstore](https://img.shields.io/badge/App_Store-0D96F6?style=flat&logo=app-store&logoColor=white)](https://apps.apple.com/no/app/glimmer-scan/id6502996383)
[![BuyMeACoffee](https://raw.githubusercontent.com/pachadotdev/buymeacoffee-badges/main/bmc-yellow.svg)](https://buymeacoffee.com/glimmer)

---

## Overview

This project is a fan-driven tool that automatically downloads, processes, and organizes the card catalog data and images for Lorcana TCG. It retrieves the latest JSON data and images, structures them by language and resolution, updates a SQLite database, and pushes the changes via GitHub Actions. This ensures that this repo always reflects the most recent catalog update.

---

## Features

- **Automated Data Retrieval:**  
  Downloads the latest card catalog from the Lorcana API.

- **Data Processing & Database Update:**  
  Extracts key fields from the JSON files (such as name, subtitle, rules text, identifiers, and more) and updates a SQLite database.

- **Image Download & Organization:**  
  Retrieves card images in multiple resolutions and organizes them into language-specific directories, including special folders for foil masks.

---

## Installation & Usage

### Local Setup

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/beingwortmann/lorcana-api.git
   cd lorcana-api
   
2. **Install Python 3.x (if not already installed).**

3. **Replace the "LORCANA_SECRET_TOKEN" in the script with your Token or define it in the Github Actions Repository secrets**

4. **Run the Script:**
   
   ```bash
   python3 sync.py
   
This will download the catalog, update the database, and download all images into the appropriate language directories.


### GitHub Actions

- The repository includes a GitHub Actions workflow that automatically:
  - Runs the sync.py script.
  - Splits commits per language to manage push sizes.
  - Pushes the updated catalog, database, and images back to the repository.
  - You can also manually trigger the workflow from the Actions tab in your GitHub repository.

 ---

## Original Source
This project is a fork and extension of the original lorcana-api repository found at https://github.com/hexastix/lorcana-api by hexastix.

---

## Legal Notice
This Project uses trademarks and/or copyrights associated with Disney Lorcana TCG,
used under Ravensburger’s Community Code Policy (https://cdn.ravensburger.com/lorcana/community-code-en).
We are expressly prohibited from charging you to use or access this content.
This Project is not published, endorsed, or specifically approved by Disney or Ravensburger.
For more information about Disney Lorcana TCG, visit https://www.disneylorcana.com/en-US/.
