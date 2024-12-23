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
# Uncomment this for headless mode:
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
    base_url = "https://scholar.google.com"

    if page_url:
        driver.get(page_url)
    else:
        url = f"{base_url}/scholar?q={query.replace(' ', '+')}"
        driver.get(url)

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

        # "Cited by" link
        cited_by_link = None
        num_citations = 0
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
            num_citations_text = cited_by_elem.text.split("Cited by")[-1].strip()
            num_citations = int(num_citations_text) if num_citations_text.isdigit() else 0
        except NoSuchElementException:
            pass

        # NEW: "All x versions" link
        versions_link = None
        try:
            versions_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "versions")  # e.g. "All 5 versions"
            versions_link = versions_elem.get_attribute("href")
        except NoSuchElementException:
            pass

        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link,
            "num_citations": num_citations,
            "is_next_page": False,
            "next_page_url": None,
            "children": [],
            "versions_link": versions_link  # NEW
        })

    # Next page
    next_page_url = None
    try:
        next_button = driver.find_element(By.LINK_TEXT, "Next")
        next_page_url = next_button.get_attribute("href")
    except NoSuchElementException:
        pass

    if next_page_url:
        results.append({
            "title": "Load Next Page >>",
            "link": "",
            "cited_by_link": None,
            "num_citations": None,
            "is_next_page": True,
            "next_page_url": next_page_url,
            "children": [],
            "versions_link": None  # NEW
        })

    return results

def get_citing_papers(cited_by_url, driver, max_results=10, page_url=None):
    if not cited_by_url and not page_url:
        return []

    driver.get(page_url if page_url else cited_by_url)
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
        num_citations = 0
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
            num_citations_text = cited_by_elem.text.split("Cited by")[-1].strip()
            num_citations = int(num_citations_text) if num_citations_text.isdigit() else 0
        except NoSuchElementException:
            pass

        # We won't parse the "All x versions" link here for citing papers, but you could
        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link,
            "num_citations": num_citations,
            "is_next_page": False,
            "next_page_url": None,
            "children": [],
            "versions_link": None  # ignoring versions in citing papers for brevity
        })

    next_page_url = None
    try:
        next_button = driver.find_element(By.LINK_TEXT, "Next")
        next_page_url = next_button.get_attribute("href")
    except NoSuchElementException:
        pass

    if next_page_url:
        results.append({
            "title": "Load Next Page >>",
            "link": "",
            "cited_by_link": None,
            "num_citations": None,
            "is_next_page": True,
            "next_page_url": next_page_url,
            "children": [],
            "versions_link": None
        })

    return results

# NEW: Function to scrape versions
def get_versions(versions_url, driver):
    """
    Scrapes all version links from the 'All x versions' page of a paper.
    Returns a list of dicts, each with:
        "title": str,
        "link": str
    """
    if not versions_url:
        return []

    driver.get(versions_url)
    time.sleep(1.5)

    results = []
    entries = driver.find_elements(By.CSS_SELECTOR, ".gs_r .gs_ri")

    for entry in entries:
        try:
            title_elem = entry.find_element(By.CSS_SELECTOR, "h3 a")
            title = title_elem.text.strip()
            link = title_elem.get_attribute("href")
            results.append({"title": title, "link": link})
        except NoSuchElementException:
            continue

    return results

###################################################
# Main Tkinter App
###################################################
class CitationExplorer(tk.Tk):
    SAVE_FILE = "tree_state.json"

    def __init__(self):
        super().__init__()
        self.title("Google Scholar Citation Explorer (Single-Column View)")
        self.geometry("1100x600")

        # Selenium driver & in-memory cache
        self.driver = init_driver()
        self.item_to_paper = {}

        self.build_controls()
        self.build_tree()
        self.create_context_menu()

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
        load_button.pack(side=tk.LEFT, padx=5)

        reset_button = ttk.Button(control_frame, text="Reset Tree", command=self.reset_tree)
        reset_button.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Enter a search query.")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)

    def build_tree(self):
        self.tree = ttk.Treeview(self)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.heading("#0", text="Papers / Citations", anchor=tk.W)

        self.tree.bind("<Double-1>", self.on_tree_item_double_click)
        self.tree.bind("<Button-3>", self.on_tree_right_click)

    def create_context_menu(self):
        self.tree_menu = tk.Menu(self, tearoff=0)
        self.tree_menu.add_command(label="Open Paper URL", command=self.on_open_paper_url)
        self.tree_menu.add_separator()

        # NEW: Show All Versions
        self.tree_menu.add_command(label="Show All Versions", command=self.on_show_all_versions)  # NEW

        self.tree_menu.add_command(label="Save Node Path to File", command=self.save_node_path_to_file)
        self.tree_menu.add_command(label="Save Tree State", command=self.save_tree_state)

    # NEW: Show All Versions handler
    def on_show_all_versions(self):
        """
        When right-click -> 'Show All Versions':
        1) Check if current paper has a versions_link.
        2) If so, scrape the version links.
        3) Show them in a popup.
        4) Let user open any link in their browser.
        """
        item_id = self._get_selected_item_id()
        if not item_id:
            self.set_status("No item selected.")
            return

        paper = self.item_to_paper.get(item_id)
        if not paper:
            self.set_status("No data in cache for this item.")
            return

        versions_url = paper.get("versions_link")
        if not versions_url:
            self.set_status("No versions link available for this paper.")
            return

        self.set_status(f"Fetching all versions for: {paper.get('title', '')}")
        versions = get_versions(versions_url, self.driver)
        if not versions:
            self.set_status("No versions found or parse error.")
            return

        popup = Toplevel(self)
        popup.title("All Versions")
        popup.geometry("600x400")

        listbox = Listbox(popup)
        listbox.pack(fill=tk.BOTH, expand=True)

        for v in versions:
            listbox.insert(END, v["link"])

        def on_select(event):
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            chosen_version = versions[index]
            url = chosen_version.get("link")
            if url:
                webbrowser.open(url)
            else:
                self.set_status("No valid link for that version.")

        listbox.bind("<Double-1>", on_select)

    ###################################################
    # Loading and resetting the Tree
    ###################################################
    def load_saved_path(self):
        file_path = tk.filedialog.askopenfilename(
            title="Load Tree State",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            self.set_status("Load operation canceled.")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                paper_list = json.load(f)
            if not paper_list:
                self.set_status("Loaded tree is empty.")
                return

            self.tree.delete(*self.tree.get_children())
            self.item_to_paper.clear()

            for paper in paper_list:
                self.insert_paper_recursive("", paper)
            self.set_status(f"Tree state successfully loaded from {file_path}")

        except Exception as e:
            self.set_status(f"Error loading tree: {e}")

    def reset_tree(self):
        self.tree.delete(*self.tree.get_children())
        self.item_to_paper.clear()
        self.set_status("Tree reset successfully.")

    def load_tree_state_on_startup(self):
        if os.path.exists(self.SAVE_FILE):
            try:
                with open(self.SAVE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.tree.delete(*self.tree.get_children())
                self.item_to_paper.clear()
                for paper in data:
                    self.insert_paper_recursive("", paper)
                self.set_status("Loaded tree from saved state.")
            except Exception as e:
                self.set_status(f"Could not load saved state: {e}")
        else:
            self.set_status("No saved state found. Ready.")

    ###################################################
    # Searching
    ###################################################
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
                next_res = search_google_scholar(
                    None,
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
        self.tree.delete(*self.tree.get_children())
        self.item_to_paper.clear()

        root_id = self.insert_paper_node("", paper)
        self.expand_citations(root_id, paper)
        self.set_status(f"Loaded root: {paper.get('title', '')}")

    ###################################################
    # Tree Insert/Expand Helpers
    ###################################################
    def insert_paper_node(self, parent_item_id, paper):
        if paper.get("is_next_page"):
            display_text = f"[NEXT PAGE] {paper['title']}"
        else:
            title_part = paper.get("title", "")
            cites = paper.get("num_citations", "N/A")
            display_text = f"{title_part}  [Citations: {cites}]"

        node_id = self.tree.insert(parent_item_id, END, text=display_text)
        self.item_to_paper[node_id] = paper
        return node_id

    def insert_paper_recursive(self, parent_item_id, paper):
        node_id = self.insert_paper_node(parent_item_id, paper)
        for child in paper.get("children", []):
            self.insert_paper_recursive(node_id, child)

    def on_tree_item_double_click(self, event):
        item_id = self.tree.focus()
        if not item_id:
            return

        paper = self.item_to_paper.get(item_id)
        if not paper:
            self.set_status("No data in cache for this item.")
            return

        if paper["is_next_page"]:
            next_url = paper.get("next_page_url")
            if not next_url:
                return
            parent_id = self.tree.parent(item_id)
            self.tree.delete(item_id)

            citing = get_citing_papers(None, self.driver, max_results=10, page_url=next_url)
            parent_paper = self.item_to_paper.get(parent_id, {})
            if "children" not in parent_paper:
                parent_paper["children"] = []
            parent_paper["children"].extend(citing)

            for c in citing:
                self.insert_paper_node(parent_id, c)
            self.set_status("Loaded next page of citing papers.")
        else:
            children = self.tree.get_children(item_id)
            if children:
                self.set_status("Already expanded.")
                return
            self.expand_citations(item_id, paper)

    def expand_citations(self, parent_item_id, paper):
        if not paper.get("children"):
            cb_link = paper.get("cited_by_link")
            if cb_link:
                self.set_status(f"Fetching citations for: {paper.get('title')}")
                citing = get_citing_papers(cb_link, self.driver, max_results=10)
                paper["children"] = citing
            else:
                paper["children"] = []

        for c_paper in paper["children"]:
            self.insert_paper_node(parent_item_id, c_paper)

        title = paper.get("title", "")
        self.set_status(f"Found {len(paper['children'])} citing papers for: {title}")

    ###################################################
    # Right-Click Functionality
    ###################################################
    def on_tree_right_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id:
            return
        self.tree.selection_set(item_id)
        self.tree_menu.post(event.x_root, event.y_root)

    def on_open_paper_url(self):
        item_id = self._get_selected_item_id()
        if not item_id:
            return
        paper = self.item_to_paper.get(item_id)
        if not paper:
            self.set_status("No data for this item.")
            return
        if paper["is_next_page"]:
            self.set_status("This is a 'Load Next Page' item, no URL to open.")
            return
        if paper.get("link"):
            webbrowser.open(paper["link"])
        else:
            self.set_status("No valid link to open.")

    def save_node_path_to_file(self):
        item_id = self._get_selected_item_id()
        if not item_id:
            self.set_status("No item selected.")
            return

        path = []
        current_id = item_id
        while current_id:
            paper = self.item_to_paper.get(current_id, {})
            if not paper:
                self.set_status("Error: Node data not found.")
                return
            path.append({
                "title": paper.get("title", ""),
                "link": paper.get("link", ""),
                "cited_by_link": paper.get("cited_by_link"),
                "is_next_page": paper.get("is_next_page", False),
                "next_page_url": paper.get("next_page_url"),
                "children": paper.get("children", []),
                "versions_link": paper.get("versions_link")  # Include versions link if you'd like
            })
            current_id = self.tree.parent(current_id)
        path.reverse()

        file_path = tk.filedialog.asksaveasfilename(
            title="Save Node Path to File",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")]
        )
        if not file_path:
            self.set_status("Save operation canceled.")
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(path, f, indent=2)
            self.set_status(f"Node path saved to {file_path}")
        except Exception as e:
            self.set_status(f"Error saving path: {e}")

    ###################################################
    # Saving / Loading Entire Tree
    ###################################################
    def save_tree_state(self):
        root_nodes = self.tree.get_children("")
        paper_list = []
        for rn in root_nodes:
            p = self.build_paper_recursive(rn)
            if p:
                paper_list.append(p)

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
        paper = self.item_to_paper.get(item_id)
        if not paper:
            return None

        result = {
            "title": paper.get("title", ""),
            "link": paper.get("link", ""),
            "cited_by_link": paper.get("cited_by_link"),
            "is_next_page": paper.get("is_next_page", False),
            "next_page_url": paper.get("next_page_url"),
            "children": [],
            "versions_link": paper.get("versions_link")  # Keep versions_link
        }

        for child_id in self.tree.get_children(item_id):
            child_data = self.build_paper_recursive(child_id)
            if child_data:
                result["children"].append(child_data)

        return result

    ###################################################
    # Utility
    ###################################################
    def _get_selected_item_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return sel[0]

    def set_status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()

    def on_closing(self):
        self.driver.quit()
        self.destroy()

if __name__ == "__main__":
    app = CitationExplorer()
    # app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
