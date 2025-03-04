# Lorcana Catalog Downloader & Processor

![Last Commit](https://img.shields.io/github/last-commit/beingwortmann/lorcana-api?style=flat-square)
![Build Status](https://img.shields.io/github/workflow/status/beingwortmann/lorcana-api/CI?style=flat-square)
![License](https://img.shields.io/github/license/beingwortmann/lorcana-api?style=flat-square)

---

## Overview

This project is a fan-driven tool that automatically downloads, processes, and organizes the card catalog data and images for Lorcana TCG. It retrieves the latest JSON data and images, structures them by language and resolution, updates a SQLite database, and pushes the changes via GitHub Actions. This ensures that your repository always reflects the most recent catalog update.

---

## Features

- **Automated Data Retrieval:**  
  Downloads the latest card catalog from the Lorcana API.

- **Data Processing & Database Update:**  
  Extracts key fields from the JSON files (such as name, subtitle, rules text, identifiers, and more) and updates a SQLite database.

- **Image Download & Organization:**  
  Retrieves card images in multiple resolutions and organizes them into language-specific directories, including special folders for foil masks.

- **Scheduled & Manual Updates:**  
  Integrated with GitHub Actions to run on a schedule as well as manually via the GitHub Actions interface.

- **Dynamic Last Updated Display:**  
  The badges at the top show the time of the last commit, giving a visual indicator of when the data was last updated.

---

## Installation & Usage

### Local Setup

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/beingwortmann/lorcana-api.git
   cd lorcana-api
   
2. **Install Python 3.x (if not already installed).**

3. **Run the Script:**
   
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
