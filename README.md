Google Scholar Citation Explorer (Single-Column View)
=====================================================

This project provides a Tkinter GUI application to explore Google Scholar citations for an article or set of articles. You can search for articles on Google Scholar, expand their citation trees, and save or load your exploration in JSON format.

Key Features
------------

*   **GUI built with Tkinter**
    
    *   A main window with a single-column `TreeView` to list papers and their citing papers.
    *   A status bar to display messages and updates.
    *   Context menu (right-click) for convenient actions like saving node paths or opening paper URLs.
*   **Search & Scrape from Google Scholar**
    
    *   Automatically uses Selenium to open a Firefox browser for scrapes (supports headless mode).
    *   Retrieves basic bibliographic information such as title, direct link, “Cited by” link, and citation count.
    *   Supports paging: if more citing papers exist, a “Load Next Page” node is automatically inserted.
*   **Node Expansion**
    
    *   Double-click on a paper to fetch its citing papers.
    *   Each citing paper can, in turn, be expanded further.
*   **Save/Load Tree State**
    
    *   Save the entire citation tree to a JSON file.
    *   Load a saved JSON citation tree to restore your exploration.
    *   Save a single node path (from root to selected node) to a JSON file.
*   **Configuration**
    
    *   A `config.json` file is used to specify the Firefox WebDriver executable path for Selenium.

* * *

Getting Started
---------------

### 1\. Prerequisites

*   **Python 3.7+**  
    Make sure you have a recent version of Python installed.
    
*   **Firefox Browser**  
    Selenium will be using Firefox. Ensure Firefox is installed on your system.
    
*   **GeckoDriver**  
    Download the appropriate GeckoDriver (Firefox WebDriver) for your operating system:  
    [https://github.com/mozilla/geckodriver/releases](https://github.com/mozilla/geckodriver/releases)
    
    Place `geckodriver` (or `geckodriver.exe` on Windows) in a known location.
    
*   **Selenium for Python**  
    Install Selenium via pip:
    
    bash
    
    Copy code
    
    `pip install selenium`
    
*   **Tkinter**  
    Tkinter usually comes bundled with most Python distributions. If it’s not available, install it according to your OS requirements.
    

### 2\. Project Structure

bash

Copy code

```
├── CitationExplorer.py   # The main script (contains the Tkinter app) 
├── config.json           # JSON config file with "firefox_driver_path" 
└── README.md             # This readme
```

**`config.json`**  
This file should contain a key `firefox_driver_path` which points to your GeckoDriver executable. Example:

json

Copy code

`{   "firefox_driver_path": "/absolute/path/to/geckodriver" }`

### 3\. Usage

1.  **Clone or Download** this repository.
    
2.  **Edit `config.json`** to provide the correct path to your GeckoDriver:
    
    json
    
    Copy code
    
    `{   "firefox_driver_path": "C:/Path/To/geckodriver.exe" }`
    
    _(On Windows, be sure to use either double backslashes `\\` or forward slashes `/`.)_
    
3.  **Run the Application**:
    
    bash
    
    Copy code
    
    `python CitationExplorer.py`
    
4.  **Search for Articles**
    
    *   Enter a query in the "Search Query" field (e.g., `machine learning` or a more specific article title).
    *   Click **Search** to open the “Search Results” popup.
    *   Double-click an entry (paper title or “\[NEXT PAGE\]” node) to load it as the root article or load additional results.
    *   Once you select a paper, the main window’s `TreeView` will populate with the paper at the root.
5.  **Explore Citations**
    
    *   Double-click on any paper in the tree to load its citations.
    *   If a node labeled “\[NEXT PAGE\]” appears, double-click it to load more pages of citing papers.
6.  **Saving and Loading**
    
    *   **Save Tree**: Saves the entire tree currently displayed.
    *   **Load Path**: Loads a previously saved JSON file containing a citation tree.
    *   **Reset Tree**: Clears all data from the tree.
    *   **Right-Click** on a node and select **“Save Node Path to File”**: Saves the path from the root down to the selected node.
7.  **Opening Paper URLs**
    
    *   Right-click on any node that represents a paper and select **“Open Paper URL”** to open the article in your default web browser (if a valid link is available).

### 4\. File & State Management

*   **In-Memory Tree**  
    The application maintains a mapping of `TreeView` item IDs to paper dictionaries (title, link, cited\_by\_link, etc.).
*   **`tree_state.json`** (Auto-Load)  
    By default, the script attempts to load a saved state on startup from `tree_state.json` in the same directory if it exists.
*   **Manual Save / Load**  
    You can choose a different file name/location for saving or loading trees via the file dialog.

### 5\. Code Overview

*   **`load_config()`**  
    Reads `config.json` to get your Firefox driver path.
*   **`init_driver()`**  
    Initializes a Selenium Firefox WebDriver (optionally headless) using the path from `config.json`.
*   **Scraping Methods**
    *   `search_google_scholar(query, driver, max_results=10, page_url=None)`
    *   `get_citing_papers(cited_by_url, driver, max_results=10, page_url=None)`  
        Both functions return lists of dictionaries with details about each paper or a “Load Next Page” placeholder.
*   **`CitationExplorer(tk.Tk)`**  
    The main Tkinter application class. Sets up the GUI elements and uses Selenium to gather data. Key methods:
    *   **`do_search()`**: Initiates a scholar search and opens a popup with the search results.
    *   **`load_root_paper()`**: Loads a selected paper as the root in the tree.
    *   **`expand_citations()`**: Fetches and appends citing papers under a selected tree node.
    *   **State Management**: `save_tree_state()`, `load_saved_path()`, `load_tree_state_on_startup()`, etc.

### 7\. Disclaimer

Google Scholar has usage limitations, and scraping may violate Google Scholar’s Terms of Service. Use at your own discretion and for educational or personal use only.

* * *

License
-------

This project is provided “as is” without warranty of any kind. You may use or modify it for your personal or research purposes.

Enjoy exploring your citation networks!