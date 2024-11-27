# Web Scraper v1.0

## Overview

Web Scraper v1.0 is a Python-based tool designed for scraping website content, including HTML pages and assets such as CSS, JavaScript, images, and fonts. The script provides features like URL validation, retry logic with exponential backoff, request throttling, and a hierarchical website map.

## Features

- **URL Validation**: Ensures the target URL is valid and accessible.
- **Retry Logic**: Automatically retries failed requests with exponential backoff.
- **Request Throttling**: Manages request intervals to avoid overwhelming servers.
- **Asset Organization**: Downloads and organizes assets into categorized folders (`js`, `css`, `images`, `fonts`).
- **Website Map**: Generates a structured map of the website, saving it in JSON and text formats.
- **Recursive Crawling**: Scrapes pages up to a specified depth while respecting the website's structure.
- **Colored Console Output**: Provides user-friendly, color-coded terminal messages using `colorama`.

---

## Installation

### Prerequisites

1. Python 3.8 or newer
2. Install dependencies via `pip`:
   ```bash
   pip install -r requirements.txt
   ```

### Required Libraries

- `requests`
- `beautifulsoup4`
- `urllib3`
- `colorama`

### Setup

Clone this repository and navigate to the folder:
```bash
git clone https://github.com/username/web-scraper.git
cd web-scraper
```

---

## Usage

Run the script:
```bash
python scraper.py
```

1. Enter the target URL when prompted.
2. The script validates the URL and creates a folder structure for storing scraped content.
3. The scraper crawls pages up to the specified depth and downloads assets.

### Customization

Modify constants in the script to customize behavior:
- **`MAX_RETRIES`**: Maximum number of retries for failed requests.
- **`INITIAL_BACKOFF`**: Initial delay in seconds for retries.
- **`MAX_BACKOFF`**: Maximum delay in seconds for retries.
- **`CONCURRENT_REQUESTS_PER_DOMAIN`**: Maximum concurrent requests per domain.

---

## Output

- **Scraped Content**: Saved in a directory named after the target website.
- **Logs**: Saved in a log file specific to the target site.
- **Website Map**:
  - JSON file (`website_map.json`): Programmatically accessible.
  - Text file (`website_structure.txt`): Human-readable format.

---

## TODO List

### Bug Fixes

1. **Remove Duplicate `setup_logging` Function**:
   - Consolidate the two definitions into one and ensure proper usage throughout the script.

2. **Global Logger Initialization**:
   - Ensure `logger` is initialized before use in all functions.

3. **Fix Path Collisions in `get_path_from_url`**:
   - Implement a more robust path generation logic to avoid file overwrites.

4. **Refactor `clean_url` Logic**:
   - Prevent over-aggressive cleaning of URLs that may alter their meaning.

---

### Improvements

1. **Add CLI Arguments**:
   - Use `argparse` to allow users to specify:
     - Target URL
     - Output directory
     - Log level
     - Scraping depth

2. **Improve Throttling**:
   - Simplify throttling logic using libraries like `ratelimit` for better maintainability.

3. **Dynamic Directory Creation**:
   - Only create asset directories if the corresponding assets are downloaded.

4. **Retry Logic for Specific Errors**:
   - Extend retry logic to handle `429 Too Many Requests` using the `Retry-After` header.

5. **Implement Sitemap Parsing**:
   - Add support for parsing and crawling sitemaps for better coverage of large sites.

6. **Path Length Validation**:
   - Ensure unique filenames while truncating paths longer than 255 characters.

---

### Enhancements

1. **Centralize Exception Handling**:
   - Create a utility function or decorator for consistent error logging and re-raising.

2. **Improve Logging**:
   - Replace `print_colored` calls with `logging` for better debugging and log management.

3. **Add Unit Tests**:
   - Write tests for core functions like:
     - `clean_url`
     - `validate_url`
     - `get_path_from_url`
     - `download_file`

4. **Enhance Recursive Crawling**:
   - Add a dynamic limit for the number of pages to scrape.

5. **Support Config Files**:
   - Allow users to define scraper settings (e.g., depth, retries) in a configuration file.

6. **Portable Output Styles**:
   - Replace hardcoded terminal clear commands with platform-independent solutions.

---

## Example Output

```
╔══════════════════════════════════════════════════════════════════╗
║                                                                  ║
║   ██████  ▄████▄   ██▀███   ▄▄▄       ██▓███  ▓█████  ██▀███     ║
║ ▒█    ▒ ▒██▀ ▀█  ▓██ ▒ ██▒▒████▄    ▓██░  ██▒▓█   ▀ ▓██ ▒ ██▒   ║
║ ░ ▓██▄   ▒▓█    ▄ ▓██ ░▄█ ▒▒██  ▀█▄  ▓██░ ██▓▒▒███   ▓██ ░▄█ ▒   ║
║   ▒   ██▒▒▓▓▄ ▄██▒▒██▀▀█▄  ░██▄▄▄▄██ ▒██▄█▓▒ ▒▒▓█  ▄ ▒██▀▀█▄     ║
║ ▒█████▒▒▒ ▓███▀ ░░██▓ ▒██▒ ▓█   ▓██▒▒██▒ ░  ░░▒████▒░██▓ ▒██▒   ║
║ ▒ ▒▓▒ ▒ ░░ ░▒ ▒  ░░ ▒▓ ░▒▓░ ▒▒   ▓▒█░▒▓▒░ ░  ░░░ ▒░ ░░ ▒▓ ░▒▓░   ║
║ ░ ░▒  ░ ░  ░  ▒     ░▒ ░ ▒░  ▒   ▒▒ ░░▒ ░      ░ ░  ░  ░▒ ░ ▒░   ║
║ ░  ░  ░  ░          ░░   ░   ░   ▒   ░░          ░     ░░   ░    ║
║       ░  ░ ░         ░           ░  ░            ░  ░   ░        ║
║          ░                                                       ║
║                                                                  ║
║  Web Scraper v1.0                                                ║
║  Created by: Cyb3dude                                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝

ℹ Enter website URL to scrape: https://example.com
✓ URL validated successfully
📁 Base folder created at: ./example
🌐 Scraping: https://example.com
↓  Downloading: https://example.com/styles.css
📁 Created directory: ./example/assets/css
✓  Saved: styles.css
🌐 Scraping completed successfully! 🎉
```

---

## License

This project is licensed under the MIT License. Feel free to use, modify, and distribute.