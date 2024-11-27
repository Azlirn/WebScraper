# scraper.py

import os
import sys
import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from requests.exceptions import (
    RequestException, 
    MissingSchema, 
    InvalidSchema, 
    InvalidURL,
    ConnectionError,
    Timeout
)
import time
from functools import wraps
import random
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import re
import mimetypes
from colorama import init, Fore, Back, Style
import json

# Initialize colorama for cross-platform colored output
init()

def setup_logging(base_folder):
    """Set up logging with site-specific log file"""
    try:
        # Get site name from base folder
        site_name = os.path.basename(base_folder)
        
        # Create log file name based on site
        log_file = os.path.join(os.path.dirname(base_folder), f"{site_name}_scraper.log")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        print_colored(f"Logging to: {log_file}", Fore.BLUE, "info")
        return logging.getLogger(__name__)
        
    except Exception as e:
        print_colored(f"Error setting up logging: {e}", Fore.RED, "error")
        raise

# Constants for retry and throttling
MAX_RETRIES = 3
INITIAL_BACKOFF = 2  # seconds
MAX_BACKOFF = 10  # seconds
MIN_REQUEST_INTERVAL = 0.1  # 100ms minimum delay between requests
MAX_REQUEST_INTERVAL = 0.5  # 500ms maximum delay between requests
CONCURRENT_REQUESTS_PER_DOMAIN = 3

class WebScraperError(Exception):
    """Base exception class for web scraper errors"""
    pass

class RequestThrottler:
    """Class to manage request timing and prevent overwhelming the server"""
    def __init__(self):
        self.last_request_time = {}
        self.request_counts = {}
        
    def wait(self, domain):
        """Calculate and wait appropriate time before next request"""
        current_time = time.time()
        
        # Initialize domain if not seen before
        if domain not in self.last_request_time:
            self.last_request_time[domain] = current_time
            self.request_counts[domain] = 0
            return
        
        # Calculate dynamic delay based on recent request count
        request_count = self.request_counts.get(domain, 0)
        if request_count > CONCURRENT_REQUESTS_PER_DOMAIN:
            delay = random.uniform(MIN_REQUEST_INTERVAL * 2, MAX_REQUEST_INTERVAL * 2)
        else:
            delay = random.uniform(MIN_REQUEST_INTERVAL, MAX_REQUEST_INTERVAL)
        
        # Wait if necessary
        time_since_last = current_time - self.last_request_time[domain]
        if time_since_last < delay:
            time.sleep(delay - time_since_last)
        
        # Update tracking
        self.last_request_time[domain] = time.time()
        self.request_counts[domain] = request_count + 1

# Create global throttler instance
throttler = RequestThrottler()

def retry_with_backoff(retries=MAX_RETRIES, backoff_in_seconds=INITIAL_BACKOFF):
    """Decorator for implementing retry logic with exponential backoff"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Initialize variables
            total_retries = 0
            current_backoff = backoff_in_seconds
            
            while total_retries <= retries:
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, Timeout, RequestException) as e:
                    if total_retries == retries:
                        logger.error(f"Max retries ({retries}) reached for {func.__name__}")
                        raise e
                    
                    total_retries += 1
                    wait_time = min(current_backoff * (2 ** (total_retries - 1)), MAX_BACKOFF)
                    logger.warning(f"Attempt {total_retries} failed, retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            
            return None
        return wrapper
    return decorator

def create_session():
    """Create a requests session with retry configuration"""
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=INITIAL_BACKOFF,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def clean_url(url):
    """Clean and normalize URL format"""
    try:
        # Remove any leading/trailing whitespace
        url = url.strip()
        
        # Remove any leading @ or other invalid characters
        url = re.sub(r'^[@#]+', '', url)
        
        # Remove anchor fragments (#content, #top, etc.)
        url = url.split('#')[0]
        
        # Ensure proper protocol
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url.lstrip('/')
        
        # Parse the URL
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Handle the homepage specially
        if not path or path == 'index.html':
            return f"{parsed.scheme}://{parsed.netloc}"
            
        # Split path and get the last segment
        path_parts = path.split('/')
        
        # Remove .html if present in any part
        path_parts = [p[:-5] if p.endswith('.html') else p for p in path_parts]
        
        # Create new path by joining all parts with hyphens
        new_path = '-'.join(filter(None, path_parts))
        
        # Reconstruct URL
        url = f"{parsed.scheme}://{parsed.netloc}/{new_path}"
        
        print_colored(f"Cleaned URL: {url}", Fore.BLUE, "info")
        return url
        
    except Exception as e:
        print_colored(f"Error cleaning URL {url}: {e}", Fore.RED, "error")
        raise

def validate_url(url):
    """Validate URL format and accessibility"""
    try:
        # Clean the URL first
        url = clean_url(url)
        
        # Basic format validation
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            raise WebScraperError("Invalid URL format")
        
        # Check if URL is accessible
        session = create_session()
        response = session.head(url, allow_redirects=True, timeout=30)
        response.raise_for_status()
        
        return url
        
    except (MissingSchema, InvalidSchema, InvalidURL) as e:
        raise WebScraperError(f"Invalid URL format: {e}")
    except ConnectionError:
        raise WebScraperError("Could not connect to the website")
    except Timeout:
        raise WebScraperError("Connection timed out")
    except RequestException as e:
        raise WebScraperError(f"Error accessing URL: {e}")

def get_safe_filename(url):
    """Convert URL to a safe directory name without TLD"""
    try:
        domain = urlparse(url).netloc
        domain = domain.replace('www.', '')
        # Remove TLD (everything after the last dot)
        domain = domain.rsplit('.', 1)[0]
        # Replace remaining invalid characters
        safe_name = re.sub(r'[^a-zA-Z0-9-]', '_', domain)
        print(f"Creating folder for website: {safe_name}")
        return safe_name
    except Exception as e:
        print(f"Error creating folder name: {e}")
        raise

def create_directory(path):
    """Create a directory if it doesn't exist"""
    try:
        # Get absolute path to script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Create full path
        full_path = os.path.join(script_dir, path)
        
        # Create directory if it doesn't exist
        if not os.path.exists(full_path):
            os.makedirs(full_path)
            print(f"Created folder: {full_path}")
        return full_path
    except Exception as e:
        print(f"Error creating directory: {e}")
        raise

def setup_website_folders(url):
    """Set up the initial folder structure"""
    try:
        # Create main website folder
        base_folder = get_safe_filename(url)
        base_path = create_directory(base_folder)
        print(f"Created main website folder: {base_path}")
        
        # Create assets folder structure
        assets_path = os.path.join(base_folder, 'assets')
        create_directory(assets_path)
        print(f"Created assets folder: {assets_path}")
        
        # Create subfolders for different asset types
        asset_types = ['js', 'css', 'images', 'fonts']
        for asset_type in asset_types:
            asset_path = os.path.join(assets_path, asset_type)
            create_directory(asset_path)
            print(f"Created {asset_type} folder: {asset_path}")
        
        return base_path
    except Exception as e:
        print(f"Error setting up folders: {e}")
        raise

def get_path_from_url(url, base_folder):
    """Extract and clean the path from URL"""
    try:
        parsed = urlparse(url)
        path = parsed.path.strip('/')
        
        # Handle the homepage (empty path or just /)
        if not path:
            return os.path.join(base_folder, 'index.html')
        
        # Split path and get the last segment
        path_parts = path.split('/')
        
        # Join all parts with hyphens to create a flat structure
        flat_path = '-'.join(filter(None, path_parts))
        
        # Add .html extension if not present
        if not flat_path.endswith('.html'):
            flat_path += '.html'
        
        full_path = os.path.join(base_folder, flat_path)
        print_colored(f"Creating path: {full_path}", Fore.BLUE, "info")
        return full_path
        
    except Exception as e:
        print_colored(f"Error creating path from URL {url}: {e}", Fore.RED, "error")
        raise

def create_asset_directory(base_folder, asset_type):
    """Create and return path for different asset types"""
    try:
        # Ensure we're using the correct base folder
        asset_folder = os.path.join(base_folder, 'assets', asset_type)
        if not os.path.exists(asset_folder):
            os.makedirs(asset_folder, exist_ok=True)
            print(f"Created asset directory: {asset_folder}")
        return asset_folder
    except Exception as e:
        print(f"Error creating asset directory for {asset_type}: {e}")
        raise

def update_html_links(soup, original_url, base_folder):
    """Update HTML links to point to the correct local paths"""
    domain = urlparse(original_url).netloc
    
    # Update internal page links
    for a in soup.find_all('a', href=True):
        try:
            href = a['href']
            if href.startswith(('http://', 'https://')):
                # Only modify internal links
                if urlparse(href).netloc == domain:
                    # Clean the URL and add .html if needed
                    local_path = get_path_from_url(href, '')  # Empty base for relative path
                    a['href'] = os.path.relpath(local_path, os.path.dirname(base_folder))
            elif href.startswith('/'):
                # Convert absolute paths to relative
                clean_path = href.strip('/')
                if not clean_path.endswith('.html'):
                    clean_path = f"{clean_path}.html"
                a['href'] = clean_path
        except Exception as e:
            logger.error(f"Error updating link {href}: {str(e)}")
    
    # Update images with relative paths
    for img in soup.find_all('img', src=True):
        try:
            throttler.wait(domain)
            asset_url = urljoin(original_url, img['src'])
            local_path = download_file(asset_url, base_folder, 'images')
            if local_path:
                # Make path relative to current page
                rel_path = os.path.relpath(local_path, os.path.dirname(base_folder))
                img['src'] = rel_path.replace('\\', '/')
        except Exception as e:
            logger.error(f"Error updating image link {img['src']}: {str(e)}")

    # Update stylesheets with relative paths
    for link in soup.find_all('link', href=True):
        try:
            if 'stylesheet' in link.get('rel', []):
                throttler.wait(domain)
                asset_url = urljoin(original_url, link['href'])
                local_path = download_file(asset_url, base_folder, 'css')
                if local_path:
                    rel_path = os.path.relpath(local_path, os.path.dirname(base_folder))
                    link['href'] = rel_path.replace('\\', '/')
        except Exception as e:
            logger.error(f"Error updating stylesheet link {link['href']}: {str(e)}")

    # Update scripts with relative paths
    for script in soup.find_all('script', src=True):
        try:
            throttler.wait(domain)
            asset_url = urljoin(original_url, script['src'])
            local_path = download_file(asset_url, base_folder, 'js')
            if local_path:
                rel_path = os.path.relpath(local_path, os.path.dirname(base_folder))
                script['src'] = rel_path.replace('\\', '/')
        except Exception as e:
            logger.error(f"Error updating script link {script['src']}: {str(e)}")

    return soup

@retry_with_backoff()
def download_file(url, base_folder, asset_type=None, website_map=None):
    """Download a file with proper directory structure"""
    try:
        print_colored(f"  Downloading: {url}", Fore.CYAN, "download")
        
        domain = urlparse(url).netloc
        throttler.wait(domain)
        
        session = create_session()
        response = session.get(url, timeout=30)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        
        # Determine the appropriate directory
        target_dir = None
        if asset_type:
            target_dir = os.path.join(base_folder, 'assets', asset_type)
            print(f"Saving asset to: {target_dir}")
        else:
            # Determine directory based on content type
            if 'javascript' in content_type or url.endswith('.js'):
                target_dir = os.path.join(base_folder, 'assets', 'js')
            elif 'css' in content_type or url.endswith('.css'):
                target_dir = os.path.join(base_folder, 'assets', 'css')
            elif any(ext in content_type for ext in ['image', 'img', 'png', 'jpg', 'jpeg', 'gif', 'svg']):
                target_dir = os.path.join(base_folder, 'assets', 'images')
            elif 'font' in content_type or any(url.endswith(ext) for ext in ['.woff', '.woff2', '.ttf', '.eot']):
                target_dir = os.path.join(base_folder, 'assets', 'fonts')
            else:
                target_dir = get_path_from_url(url, base_folder)
        
        # Create directory if it doesn't exist
        os.makedirs(target_dir, exist_ok=True)
        print(f"Created/Using directory: {target_dir}")
        
        # Get filename from URL
        filename = os.path.basename(urlparse(url).path)
        if not filename:
            if 'html' in content_type:
                filename = 'index.html'
            else:
                ext = mimetypes.guess_extension(content_type) or ''
                filename = f'asset_{hash(url)}{ext}'
        
        # Create full file path
        filepath = os.path.join(target_dir, filename)
        
        # Ensure the file path is not too long
        if len(filepath) > 255:
            name, ext = os.path.splitext(filename)
            filepath = os.path.join(target_dir, f"{name[:240]}{ext}")
        
        # Save the file
        with open(filepath, 'wb') as f:
            f.write(response.content)
        print_colored(f"  Saved: {filename}", Fore.GREEN, "success")
        print_colored(f"    To: {target_dir}", Fore.MAGENTA, "folder")
        
        # Add asset to website map
        if website_map and asset_type:
            website_map.add_asset(url, filepath, asset_type)
        
        return filepath
        
    except Exception as e:
        print_colored(f"  Failed to download {url}: {e}", Fore.RED, "error")
        logger.error(f"Failed to download {url}: {e}")
        return None

def try_url_variations(session, base_url):
    """Try different variations of the URL to find the working one"""
    variations = [
        base_url,                    # Original URL
        base_url.rstrip('.html'),    # Without .html
        f"{base_url}.html",          # With .html
        f"{base_url}/",              # With trailing slash
    ]
    
    for url in variations:
        try:
            print_colored(f"Trying URL: {url}", Fore.BLUE, "info")
            response = session.get(url, timeout=30, allow_redirects=True)
            
            # Check if we got redirected
            if response.history:
                final_url = response.url
                print_colored(f"Redirected to: {final_url}", Fore.YELLOW, "info")
                return response, final_url
            
            # If the request was successful
            if response.status_code == 200:
                return response, url
                
        except Exception as e:
            continue
            
    return None, None

def scrape_website(url, base_folder, depth=0, max_depth=3, visited=None, website_map=None):
    """Scrape website content recursively"""
    if visited is None:
        visited = set()
    
    # Clean the URL before processing
    url = clean_url(url)
    
    # Skip if already visited
    if url in visited:
        print_colored(f"Skipping already visited: {url}", Fore.YELLOW, "info")
        return
    
    if depth > max_depth:
        return
    
    try:
        print_colored(f"Scraping: {url}", Fore.CYAN, "scraping")
        logger.info(f"Scraping: {url}")
        
        # Get the HTML file path for this URL
        html_file = get_path_from_url(url, base_folder)
        
        # Skip if the file already exists
        if os.path.exists(html_file):
            print_colored(f"File already exists: {html_file}", Fore.YELLOW, "info")
            visited.add(url)
            return
        
        # Create the directory if it doesn't exist
        os.makedirs(os.path.dirname(html_file), exist_ok=True)
        print_colored(f"Using path: {html_file}", Fore.MAGENTA, "folder")
        
        # Try different URL variations
        session = create_session()
        response, working_url = try_url_variations(session, url)
        
        if response is None:
            print_colored(f"Could not access any variation of: {url}", Fore.RED, "error")
            return
            
        # Add the working URL to visited set
        visited.add(working_url)
        visited.add(url)  # Add original URL too
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Update all asset links in HTML
        soup = update_html_links(soup, working_url, base_folder)
        
        # Save the HTML file
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print_colored(f'Saved page: {html_file}', Fore.GREEN, "success")
        
        # Add to website map
        if website_map:
            website_map.add_page(working_url, html_file)
        
        # Find and scrape linked pages
        for link in soup.find_all('a', href=True):
            try:
                href = link['href']
                # Skip anchor links and empty hrefs
                if not href or href.startswith('#'):
                    continue
                    
                page_url = urljoin(working_url, href)
                if urlparse(page_url).netloc == urlparse(working_url).netloc:
                    scrape_website(page_url, base_folder, depth + 1, max_depth, visited, website_map)
            except Exception as e:
                print_colored(f"Error processing link {link}: {e}", Fore.RED, "error")
                continue
                
    except Exception as e:
        print_colored(f"Error scraping {url}: {e}", Fore.RED, "error")

def print_header():
    """Print a fancy terminal header"""
    header = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════════════════╗
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
║  {Fore.GREEN}Web Scraper v1.0{Fore.CYAN}                                                ║
║  {Fore.WHITE}Created by: Cyb3dude{Fore.CYAN}                                            ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝{Style.RESET_ALL}"""
    print(header)

def print_colored(message, color=Fore.WHITE, status=None, newline=True):
    """Print colored and formatted messages with consistent status symbols"""
    status_icons = {
        "success": f"{Fore.GREEN}✓",  # Check mark for success
        "error": f"{Fore.RED}✗",      # X mark for errors
        "info": f"{Fore.BLUE}ℹ",      # Info symbol
        "warning": f"{Fore.YELLOW}⚠",  # Warning symbol
        "download": f"{Fore.CYAN}↓",   # Download arrow
        "folder": f"{Fore.MAGENTA}📁", # Folder icon
        "scraping": f"{Fore.CYAN}🌐",  # Web icon
        "processing": f"{Fore.BLUE}⚙",  # Processing/gear icon
        "link": f"{Fore.CYAN}→",       # Right arrow for links
        "asset": f"{Fore.BLUE}📎",     # Paperclip for assets
    }
    
    indent = "  " * message.count("  ")  # Preserve indentation
    prefix = f"{status_icons[status]}{Style.RESET_ALL} " if status else ""
    end = "\n" if newline else ""
    print(f"{indent}{prefix}{color}{message.strip()}{Style.RESET_ALL}", end=end)

class WebsiteMap:
    def __init__(self, base_url, base_folder):
        self.base_url = base_url
        self.base_folder = base_folder
        self.pages = {}  # Store page URLs and their local paths
        self.assets = {}  # Store asset URLs and their local paths
        self.structure = {  # Store hierarchical structure
            'pages': {},
            'assets': {
                'js': [],
                'css': [],
                'images': [],
                'fonts': []
            }
        }
        
    def add_page(self, url, local_path):
        """Add a page to the website map"""
        self.pages[url] = local_path
        # Add to structure
        path_parts = urlparse(url).path.strip('/').split('/')
        current_dict = self.structure['pages']
        for part in path_parts:
            if not part:
                continue
            if part not in current_dict:
                current_dict[part] = {}
            current_dict = current_dict[part]
        current_dict['_file'] = local_path
        
    def add_asset(self, url, local_path, asset_type):
        """Add an asset to the website map"""
        self.assets[url] = {
            'path': local_path,
            'type': asset_type
        }
        self.structure['assets'][asset_type].append(local_path)
        
    def save_map(self):
        """Save the website map to files"""
        try:
            # Save as JSON for programmatic access
            map_file = os.path.join(self.base_folder, 'website_map.json')
            with open(map_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'base_url': self.base_url,
                    'base_folder': self.base_folder,
                    'pages': self.pages,
                    'assets': self.assets,
                    'structure': self.structure
                }, f, indent=2)
            print_colored(f"Saved website map to: {map_file}", Fore.GREEN, "success")
            
            # Save as human-readable text
            structure_file = os.path.join(self.base_folder, 'website_structure.txt')
            with open(structure_file, 'w', encoding='utf-8') as f:
                f.write(f"Website Structure for: {self.base_url}\n")
                f.write("=" * 50 + "\n\n")
                
                f.write("Pages:\n")
                for url, path in self.pages.items():
                    f.write(f"  {url} -> {path}\n")
                
                f.write("\nAssets:\n")
                for asset_type in self.structure['assets']:
                    f.write(f"\n  {asset_type.upper()}:\n")
                    for path in self.structure['assets'][asset_type]:
                        f.write(f"    {path}\n")
            
            print_colored(f"Saved readable structure to: {structure_file}", Fore.GREEN, "success")
            
        except Exception as e:
            print_colored(f"Error saving website map: {e}", Fore.RED, "error")

def setup_logging(base_folder):
    """Set up logging with site-specific log file"""
    try:
        # Get site name from base folder
        site_name = os.path.basename(base_folder)
        
        # Create log file name based on site
        log_file = os.path.join(os.path.dirname(base_folder), f"{site_name}_scraper.log")
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        print_colored(f"Logging to: {log_file}", Fore.BLUE, "info")
        return logging.getLogger(__name__)
        
    except Exception as e:
        print_colored(f"Error setting up logging: {e}", Fore.RED, "error")
        raise

def main():
    """Main function to run the scraper"""
    try:
        # Clear screen
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # Print fancy header
        print_header()
        
        # Get the script's location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print_colored(f"Script running from: {script_dir}", Fore.BLUE, "info")
        
        # Get target URL
        print()
        print_colored("Enter website URL to scrape: ", Fore.CYAN, newline=False)
        target_url = input().strip()
        
        # Validate URL
        validate_url(target_url)
        print_colored("URL validated successfully", Fore.GREEN, "success")
        
        # Set up folder structure
        print()
        print_colored("Setting up folder structure...", Fore.BLUE, "info")
        base_path = setup_website_folders(target_url)
        print_colored(f"Base folder created at: {base_path}", Fore.GREEN, "success")
        
        # Setup logging with site-specific file
        global logger
        logger = setup_logging(base_path)
        
        # Create website map
        website_map = WebsiteMap(target_url, base_path)
        
        # Start scraping
        print_colored("Starting web scrape...", Fore.BLUE, "info")
        scrape_website(target_url, base_path, website_map=website_map)
        
        # Save the website map
        print_colored("\nSaving website structure...", Fore.BLUE, "info")
        website_map.save_map()
        
        print_colored("Scraping completed successfully! 🎉", Fore.GREEN, "success")
        
    except WebScraperError as e:
        print_colored(f"Error: {e}", Fore.RED, "error")
        sys.exit(1)
    except KeyboardInterrupt:
        print()
        print_colored("Scraping interrupted by user", Fore.YELLOW, "warning")
        sys.exit(1)
    except Exception as e:
        print_colored(f"Unexpected error: {e}", Fore.RED, "error")
        sys.exit(1)

if __name__ == '__main__':
    main()