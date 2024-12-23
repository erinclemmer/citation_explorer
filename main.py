import tkinter as tk
from tkinter.filedialog import asksaveasfilename
from tkinter import ttk, Toplevel, Listbox, END
import json
import os
import time
import webbrowser

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService


###################################################
# Load Firefox Driver Path from JSON Config
###################################################
CONFIG_FILE = "config.json"

def load_config():
    """Load configuration from a JSON file."""
    try:
        with open(CONFIG_FILE, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file '{CONFIG_FILE}' not found.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Error parsing '{CONFIG_FILE}': {e}")

config = load_config()
FIREFOX_DRIVER_PATH = config.get("firefox_driver_path")
if not FIREFOX_DRIVER_PATH:
    raise ValueError("Missing 'firefox_driver_path' in configuration file.")

###################################################
# Configure Selenium for Firefox
###################################################

firefox_options = FirefoxOptions()
# If you want headless mode (invisible browser):
# firefox_options.add_argument("--headless")

def init_driver():
    """Initialize a Firefox WebDriver instance and return it."""
    service = FirefoxService(executable_path=FIREFOX_DRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=firefox_options)
    return driver

###################################################
# Google Scholar Scraping Helpers
###################################################
def search_google_scholar(query, driver, max_results=10, page_url=None):
    """
    Searches or loads a page on Google Scholar, returns a list of dicts:
      { "title", "link", "cited_by_link", "is_next_page", "next_page_url" }
    Possibly includes a "Load Next Page >>" item at the end if there's a "Next" link.
    """
    base_url = "https://scholar.google.com"
    if page_url:
        driver.get(page_url)
    else:
        # new search
        url = f"{base_url}/scholar?q={query.replace(' ', '+')}"
        driver.get(url)

    time.sleep(1.5)  # Let the page load

    results = []
    entries = driver.find_elements(By.CSS_SELECTOR, ".gs_r .gs_ri")

    for entry in entries[:max_results]:
        try:
            title_elem = entry.find_element(By.CSS_SELECTOR, "h3 a")
            title = title_elem.text.strip()
            link = title_elem.get_attribute("href")
        except NoSuchElementException:
            continue

        cited_by_link = None
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
        except NoSuchElementException:
            pass

        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link,
            "is_next_page": False,
            "next_page_url": None,
            "children": []  # We'll store child nodes here for JSON saving
        })

    # If there's a Next link, add a special item
    next_page_url = None
    try:
        next_button = driver.find_element(By.LINK_TEXT, "Next")
        next_page_url = next_button.get_attribute("href")
    except NoSuchElementException:
        pass

    if next_page_url:
        results.append({
            "title": "Load Next Page >>",
            "link": None,
            "cited_by_link": None,
            "is_next_page": True,
            "next_page_url": next_page_url,
            "children": []
        })

    return results

def get_citing_papers(cited_by_url, driver, max_results=10, page_url=None):
    """
    Given a 'Cited by' URL or a next-page URL, scrape the citing papers from
    that page. Returns a list of dicts (similar structure to search_google_scholar()).
    """
    if not cited_by_url and not page_url:
        return []

    if page_url:
        driver.get(page_url)
    else:
        driver.get(cited_by_url)

    time.sleep(1.5)

    results = []
    entries = driver.find_elements(By.CSS_SELECTOR, ".gs_r .gs_ri")
    
    for entry in entries[:max_results]:
        try:
            title_elem = entry.find_element(By.CSS_SELECTOR, "h3 a")
            title = title_elem.text.strip()
            link = title_elem.get_attribute("href")
        except NoSuchElementException:
            continue

        cited_by_link = None
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
        except NoSuchElementException:
            pass

        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link,
            "is_next_page": False,
            "next_page_url": None,
            "children": []
        })

    # Next link?
    next_page_url = None
    try:
        next_button = driver.find_element(By.LINK_TEXT, "Next")
        next_page_url = next_button.get_attribute("href")
    except NoSuchElementException:
        pass

    if next_page_url:
        results.append({
            "title": "Load Next Page >>",
            "link": None,
            "cited_by_link": None,
            "is_next_page": True,
            "next_page_url": next_page_url,
            "children": []
        })

    return results

###################################################
# Main Tkinter App
###################################################
class CitationExplorer(tk.Tk):
    SAVE_FILE = "tree_state.json"

    def __init__(self):
        super().__init__()
        self.title("Google Scholar Citation Explorer with Right-Click Menu")
        self.geometry("1100x600")

        # Driver & cache
        self.driver = init_driver()
        # citations_cache: dict keyed by (link, title) -> dict with paper info & "children"
        self.citations_cache = {}

        # Build UI
        self.build_controls()
        self.build_tree()

        # Create a right-click menu
        self.create_context_menu()

        # Attempt to load any previously saved state
        self.load_tree_state_on_startup()

    def build_controls(self):
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Search Query:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        search_button = ttk.Button(control_frame, text="Search", command=self.do_search)
        search_button.pack(side=tk.LEFT, padx=5)

        save_button = ttk.Button(control_frame, text="Save Tree", command=self.save_tree_state)
        save_button.pack(side=tk.LEFT, padx=5)

        load_button = ttk.Button(control_frame, text="Load Path", command=self.load_saved_path)
        load_button.pack(side=tk.LEFT, padx=5)  # Add the new button here

        reset_button = ttk.Button(control_frame, text="Reset Tree", command=self.reset_tree)
        reset_button.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Enter a search query.")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)

    def load_saved_path(self):
        """
        Load a saved tree state from a file and reconstruct it with all citations.
        """
        file_path = tk.filedialog.askopenfilename(
            title="Load Tree State",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            self.set_status("Load operation canceled.")
            return

        try:
            # Load the full tree structure
            with open(file_path, "r", encoding="utf-8") as f:
                paper_list = json.load(f)

            if not paper_list:
                self.set_status("Loaded tree is empty.")
                return

            # Clear the current tree and citations cache
            self.tree.delete(*self.tree.get_children())
            self.citations_cache.clear()

            # Reconstruct the tree
            for paper in paper_list:
                self.insert_paper_recursive("", paper)  # parent="" for root-level papers

            self.set_status(f"Tree state successfully loaded from {file_path}")
        except Exception as e:
            self.set_status(f"Error loading tree: {e}")

    def reset_tree(self):
        """
        Clears the tree and resets the citations cache.
        """
        self.tree.delete(*self.tree.get_children())  # Clear all nodes from the tree
        self.citations_cache.clear()  # Reset the cache
        self.set_status("Tree reset successfully.")

    def build_tree(self):
        self.tree = ttk.Treeview(self, columns=("title",), selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.heading("#0", text="Paper Link / Special", anchor=tk.W)
        self.tree.heading("title", text="Title", anchor=tk.W)

        self.tree.column("#0", width=450, stretch=False)
        self.tree.column("title", width=600, stretch=True)

        # Double-click expand
        self.tree.bind("<Double-1>", self.on_tree_item_double_click)
        # Right-click event
        self.tree.bind("<Button-3>", self.on_tree_right_click)

    def create_context_menu(self):
        """
        Creates a context menu that will show when right-clicking on a tree item.
        """
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Open Paper URL", command=self.on_open_paper_url)
        self.tree_menu.add_separator()
        self.tree_menu.add_command(label="Save Node Path to File", command=self.save_node_path_to_file)
        self.tree_menu.add_command(label="Save Tree State", command=self.save_tree_state)

    def save_node_path_to_file(self):
        """
        Saves the selected node's path (root to selected node) to a file, including
        all relevant data such as `is_next_page` and `children`.
        """
        item_id = self.tree.selection()
        if not item_id:
            self.set_status("No item selected.")
            return

        # Gather path from root to selected item
        path = []
        current_id = item_id[0]
        while current_id:
            link = self.tree.item(current_id, "text")
            title = self.tree.item(current_id, "values")[0]
            paper_key = (link, title)

            # Retrieve the paper data from the cache
            paper = self.citations_cache.get(paper_key, {})
            if not paper:
                self.set_status("Error: Node data not found in cache.")
                return

            # Create a copy of the paper with all relevant fields
            node_data = {
                "title": paper.get("title", ""),
                "link": paper.get("link", ""),
                "cited_by_link": paper.get("cited_by_link"),
                "is_next_page": paper.get("is_next_page", False),
                "next_page_url": paper.get("next_page_url"),
                "children": paper.get("children", [])  # Include children
            }
            path.append(node_data)

            # Move to the parent node
            current_id = self.tree.parent(current_id)

        # Reverse path to go root -> selected
        path.reverse()

        # Use file dialog to select save location
        file_path = tk.filedialog.asksaveasfilename(
            title="Save Node Path to File",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            self.set_status("Save operation canceled.")
            return

        # Save to file
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(path, f, indent=2)
            self.set_status(f"Node path saved to {file_path}")
        except Exception as e:
            self.set_status(f"Error saving path: {e}")

    ######################
    # Right-Click Handler
    ######################
    def on_tree_right_click(self, event):
        """
        Right-click (Button-3) handler. We select the clicked item and show the menu.
        """
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return  # clicked on empty space, no item

        # Select this item in the tree
        self.tree.selection_set(item_id)
        
        # Show the context menu
        self.tree_menu.post(event.x_root, event.y_root)

    def on_open_paper_url(self):
        """
        Called by right-click menu -> "Open Paper URL".
        We open the paper's link in the default browser.
        """
        # Which item is selected?
        item_id = self.tree.selection()
        if not item_id:
            return

        item_id = item_id[0]
        link = self.tree.item(item_id, "text")
        title = self.tree.item(item_id, "values")[0]
        paper_key = (link, title)

        paper = self.citations_cache.get(paper_key)
        if not paper:
            self.set_status("No data in cache for this item.")
            return

        # If it's a normal paper, link should be valid
        if paper["is_next_page"]:
            self.set_status("This is a 'Load Next Page' item, no URL to open.")
            return

        if paper["link"]:
            webbrowser.open(paper["link"])
        else:
            self.set_status("No valid link to open.")

    ######################
    # Tree Loading & Saving
    ######################
    def load_tree_state_on_startup(self):
        """
        Called in __init__. If SAVE_FILE exists, try to load it and reconstruct the tree.
        """
        if os.path.exists(self.SAVE_FILE):
            try:
                with open(self.SAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Data is the entire root set or a single root?
                # We'll assume we saved a list of root-level papers
                self.tree.delete(*self.tree.get_children())
                self.citations_cache.clear()

                # Insert each top-level paper
                for paper in data:
                    self.insert_paper_recursive("", paper)  # parent=""
                
                self.set_status("Loaded tree from saved state.")
            except Exception as e:
                self.set_status(f"Could not load saved state: {e}")
        else:
            self.set_status("No saved state found. Ready.")

    def insert_paper_recursive(self, parent_item_id, paper):
        """
        Recursively insert 'paper' (dict) into the TreeView under 'parent_item_id'.
        Also store in citations_cache, then handle its children.
        """
        text = "[NEXT PAGE]" if paper["is_next_page"] else (paper["link"] or "")
        val = "Load Next Page >>" if paper["is_next_page"] else (paper["title"] or "")

        node_id = self.tree.insert(parent_item_id, tk.END, text=text, values=(val,), open=False)

        # Store in cache
        key = (text, val)
        self.citations_cache[key] = paper

        # Recurse for children
        for child in paper.get("children", []):
            self.insert_paper_recursive(node_id, child)

    def save_tree_state(self):
        """
        Gathers the entire tree from self.citations_cache, organizes it into a structure
        with 'children', and writes to JSON file self.SAVE_FILE.
        """
        root_nodes = self.tree.get_children("")
        paper_list = []
        for root_node in root_nodes:
            paper_dict = self.build_paper_recursive(root_node)
            if paper_dict:
                paper_list.append(paper_dict)

        file_path = asksaveasfilename(
            title="Save Tree State",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            self.set_status("Save operation canceled.")
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(paper_list, f, indent=2)
            self.set_status(f"Tree state saved to {file_path}")
        except Exception as e:
            self.set_status(f"Error saving tree: {e}")


    def build_paper_recursive(self, item_id):
        """
        Given a tree item_id, find its key, get the paper from the cache,
        then recursively build a dict with paper + 'children': [...]
        """
        link = self.tree.item(item_id, "text")
        title = self.tree.item(item_id, "values")[0]
        paper_key = (link, title)

        # Retrieve the paper from the cache
        paper = self.citations_cache.get(paper_key)
        if not paper:
            return None

        # Create a copy of the paper with all required fields
        result = {
            "title": paper.get("title", ""),
            "link": paper.get("link", ""),
            "cited_by_link": paper.get("cited_by_link"),
            "is_next_page": paper.get("is_next_page", False),
            "next_page_url": paper.get("next_page_url"),
            "children": []  # Populate children recursively
        }

        # Recursively build children
        child_ids = self.tree.get_children(item_id)
        for child_id in child_ids:
            child_dict = self.build_paper_recursive(child_id)
            if child_dict:
                result["children"].append(child_dict)

        return result

    ######################
    # Searching
    ######################
    def do_search(self):
        query = self.search_var.get().strip()
        if not query:
            self.set_status("Please enter a query.")
            return

        self.set_status(f"Searching for: {query} ...")
        results = search_google_scholar(query, self.driver, max_results=10)
        if not results:
            self.set_status("No results or parse error.")
            return

        self.show_search_results_popup(results)

    def show_search_results_popup(self, results):
        popup = Toplevel(self)
        popup.title("Search Results")
        popup.geometry("600x400")

        listbox = Listbox(popup)
        listbox.pack(fill=tk.BOTH, expand=True)

        # Fill listbox
        for r in results:
            if r["is_next_page"]:
                listbox.insert(END, "[NEXT PAGE] " + r["title"])
            else:
                listbox.insert(END, r["title"])

        def on_select(event):
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            paper = results[index]
            if paper["is_next_page"]:
                # load next page
                next_res = search_google_scholar(
                    None,  # query
                    self.driver,
                    max_results=10,
                    page_url=paper["next_page_url"]
                )
                results.clear()
                results.extend(next_res)
                listbox.delete(0, END)
                for nr in next_res:
                    if nr["is_next_page"]:
                        listbox.insert(END, "[NEXT PAGE] " + nr["title"])
                    else:
                        listbox.insert(END, nr["title"])
            else:
                popup.destroy()
                self.load_root_paper(paper)

        listbox.bind("<Double-1>", on_select)

    def load_root_paper(self, paper):
        """
        Clears the tree, resets the cache, then inserts 'paper' as the root.
        Then calls expand_citations() if needed.
        """
        self.tree.delete(*self.tree.get_children())
        self.citations_cache.clear()

        link = paper.get("link") or ""
        title = paper.get("title") or ""
        is_next = paper.get("is_next_page", False)

        text = "[NEXT PAGE]" if is_next else link
        val = "Load Next Page >>" if is_next else title

        root_id = self.tree.insert("", tk.END, text=text, values=(val,), open=True)
        self.citations_cache[(text, val)] = paper

        # Expand it
        self.expand_citations(root_id, paper)
        self.set_status(f"Loaded root: {title}")

    ######################
    # Double-Click Expand
    ######################
    def on_tree_item_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return

        link = self.tree.item(item_id, "text")
        title = self.tree.item(item_id, "values")[0]
        paper_key = (link, title)

        if paper_key not in self.citations_cache:
            self.set_status("No data in cache for this item.")
            return

        paper = self.citations_cache[paper_key]

        # If it's a next-page item
        if paper["is_next_page"]:
            next_url = paper["next_page_url"]
            if not next_url:
                return
            parent_id = self.tree.parent(item_id)
            # Remove the "Load Next Page >>" node
            self.tree.delete(item_id)

            # Fetch next page
            citing = get_citing_papers(None, self.driver, max_results=10, page_url=next_url)

            # Parent paper
            parent_link = self.tree.item(parent_id, "text")
            parent_title = self.tree.item(parent_id, "values")[0]
            parent_key = (parent_link, parent_title)
            parent_paper = self.citations_cache.get(parent_key, {})
            if "children" not in parent_paper:
                parent_paper["children"] = []
            parent_paper["children"].extend(citing)

            # Insert them
            for c_paper in citing:
                self.insert_citing_node(parent_id, c_paper)
            
            self.set_status("Loaded next page of citing papers.")
        else:
            # Normal paper
            children = self.tree.get_children(item_id)
            if children:
                self.set_status("Already expanded.")
                return
            self.expand_citations(item_id, paper)

    def expand_citations(self, parent_item_id, paper):
        """
        If paper has no 'children', fetch them from 'cited_by_link'.
        Insert them into the tree.
        """
        if not paper.get("children"):
            cb_link = paper.get("cited_by_link")
            if cb_link:
                self.set_status(f"Fetching citations for: {paper.get('title')}")
                citing = get_citing_papers(cb_link, self.driver, max_results=10)
                paper["children"] = citing
            else:
                paper["children"] = []

        for c_paper in paper["children"]:
            self.insert_citing_node(parent_item_id, c_paper)

        title = paper.get("title", "")
        self.set_status(f"Found {len(paper['children'])} citing papers for: {title}")

    def insert_citing_node(self, parent_item_id, c_paper):
        """
        Insert a child node for c_paper under parent_item_id, store it in the cache.
        """
        is_next = c_paper.get("is_next_page", False)
        text = "[NEXT PAGE]" if is_next else (c_paper.get("link") or "")
        val = "Load Next Page >>" if is_next else (c_paper.get("title") or "")

        child_id = self.tree.insert(parent_item_id, tk.END, text=text, values=(val,), open=False)

        # Store in cache
        self.citations_cache[(text, val)] = c_paper

    ######################
    # Status
    ######################
    def set_status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()

    def on_closing(self):
        """
        If you want to auto-save on close or do a graceful driver.quit().
        """
        self.driver.quit()
        self.destroy()


if __name__ == "__main__":
    app = CitationExplorer()
    # If you want to auto-save or do something on close:
    # app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
