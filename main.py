import tkinter as tk
from tkinter import ttk, Toplevel, Listbox, END
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

# For Firefox:
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService


###################################################
# Configure Selenium for Firefox
###################################################
# Set this to your local geckodriver path:
FIREFOX_DRIVER_PATH = "C:\\Users\\alice\\Documents\\programs\\geckodriver.exe"

firefox_options = FirefoxOptions()
# If you want to run headless (no visible browser), uncomment:
# firefox_options.add_argument("--headless")


def init_driver():
    """Initialize a Firefox WebDriver instance and return it."""
    service = FirefoxService(executable_path=FIREFOX_DRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=firefox_options)
    return driver


###################################################
# Google Scholar Scraping Helpers
###################################################
def search_google_scholar(query, driver, max_results=10):
    """
    Search for `query` on Google Scholar, parse the first page,
    and return a list of dicts with 'title', 'link', 'cited_by_link'.
    Only grabs up to `max_results`.
    """
    base_url = "https://scholar.google.com"
    search_url = f"{base_url}/scholar?q={query.replace(' ', '+')}"
    driver.get(search_url)
    time.sleep(1.5)  # Small delay to let the page load (tune as needed)

    results = []
    # The search results have a class 'gs_ri' for each entry
    entries = driver.find_elements(By.CSS_SELECTOR, ".gs_r .gs_ri")
    
    for entry in entries[:max_results]:
        try:
            title_elem = entry.find_element(By.CSS_SELECTOR, "h3 a")
            title = title_elem.text.strip()
            link = title_elem.get_attribute("href")
        except NoSuchElementException:
            # Couldn’t parse properly
            continue

        # Attempt to find the "Cited by X" link
        cited_by_link = None
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
        except NoSuchElementException:
            pass

        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link
        })

    return results


def get_citing_papers(cited_by_url, driver, max_results=10):
    """
    Given a 'Cited by X' link, open it and parse the first page of citing papers.
    Returns a list of dicts { "title": ..., "link": ..., "cited_by_link": ... }
    """
    if not cited_by_url:
        return []

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

        # Attempt to find the "Cited by X" link
        cited_by_link = None
        try:
            cited_by_elem = entry.find_element(By.PARTIAL_LINK_TEXT, "Cited by")
            cited_by_link = cited_by_elem.get_attribute("href")
        except NoSuchElementException:
            pass

        results.append({
            "title": title,
            "link": link,
            "cited_by_link": cited_by_link
        })

    return results


###################################################
# Tkinter Application
###################################################
class CitationExplorer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Google Scholar Citation Explorer (Firefox)")
        self.geometry("1000x600")

        # We use a single Selenium driver for the app’s lifetime
        self.driver = init_driver()

        # Cache: dict keyed by the tuple (link, title), storing citing papers
        # so we don’t re-scrape if we expand the same node again.
        self.citations_cache = {}

        # ---------------------------
        # Top frame: search controls
        # ---------------------------
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Search Query:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        search_button = ttk.Button(control_frame, text="Search", command=self.do_search)
        search_button.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Enter a search query.")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # ---------------------------
        # Treeview for citations
        # ---------------------------
        self.tree = ttk.Treeview(self, columns=("title"), selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.heading("#0", text="Paper / Link", anchor=tk.W)
        self.tree.heading("title", text="Title", anchor=tk.W)

        self.tree.column("#0", width=400, stretch=False)
        self.tree.column("title", width=600, stretch=True)

        # Bind double-click on the tree
        self.tree.bind("<Double-1>", self.on_tree_item_double_click)

    def do_search(self):
        """Perform a Google Scholar search using the query in self.search_var."""
        query = self.search_var.get().strip()
        if not query:
            self.set_status("Please enter a query.")
            return

        self.set_status(f"Searching for: {query} ...")

        # Launch a search on Google Scholar, parse results
        results = search_google_scholar(query, self.driver, max_results=20)
        if not results:
            self.set_status("No results found or could not parse results.")
            return

        # Show a new pop-up with the search results
        self.show_search_results_popup(results)
        self.set_status(f"Found {len(results)} result(s). Select one to load its citations.")

    def show_search_results_popup(self, results):
        """
        Show a Toplevel window listing all `results`.
        When the user double-clicks an item, load that as root paper in the tree.
        """
        popup = Toplevel(self)
        popup.title("Search Results")
        popup.geometry("600x400")

        listbox = Listbox(popup)
        listbox.pack(fill=tk.BOTH, expand=True)

        # Fill the listbox
        for item in results:
            listbox.insert(END, item["title"])

        # On double-click, load the selected paper
        def on_select(event):
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            paper = results[index]  # {title, link, cited_by_link}
            popup.destroy()
            self.load_root_paper(paper)

        listbox.bind("<Double-1>", on_select)

    def load_root_paper(self, paper):
        """
        Clears the tree and loads the 'paper' (dict) as the root paper.
        Then fetches its citations (i.e., the papers citing it).
        """
        self.tree.delete(*self.tree.get_children())
        self.citations_cache.clear()

        # Insert the root node
        root_text = paper.get("link", "No Link")
        root_title = paper.get("title", "No Title")
        root_node = self.tree.insert("", tk.END, text=root_text, values=(root_title,), open=True)

        # Expand citations for this root paper
        self.expand_citations(root_node, paper)
        self.set_status(f"Loaded root paper: {root_title}")

    def on_tree_item_double_click(self, event):
        """
        When user double-clicks a node, expand its citations if not already expanded.
        """
        item_id = self.tree.focus()
        if not item_id:
            return

        # If it already has children, assume we've expanded it
        if self.tree.get_children(item_id):
            return

        link = self.tree.item(item_id, "text")
        title = self.tree.item(item_id, "values")[0]

        # We'll store the paper in a dict to pass to expand_citations
        # We used the (link, title) as a key in the cache dictionary.
        paper_key = (link, title)
        paper_dict = self.citations_cache.get(paper_key)
        if paper_dict is None:
            self.set_status("No 'Cited by' link found or not cached.")
            return

        self.expand_citations(item_id, paper_dict)

    def expand_citations(self, parent_item_id, paper):
        """
        Fetch the citing papers for `paper` if not already done,
        insert them as children under the node `parent_item_id`.
        """
        link = paper.get("link", "")
        title = paper.get("title", "")
        paper_key = (link, title)

        # If we haven’t retrieved "citing" yet, do it now
        if "citing" not in paper:
            cited_by_url = paper.get("cited_by_link")
            if cited_by_url:
                self.set_status(f"Fetching citations for: {title}")
                citing_papers = get_citing_papers(cited_by_url, self.driver, max_results=10)
                paper["citing"] = citing_papers
            else:
                paper["citing"] = []

            # Store the updated paper in our cache
            self.citations_cache[paper_key] = paper

        citing_papers = paper["citing"]

        # Insert each citing paper into the tree
        for citing_paper in citing_papers:
            child_link = citing_paper.get("link", "")
            child_title = citing_paper.get("title", "")
            child_id = self.tree.insert(
                parent_item_id,
                tk.END,
                text=child_link,
                values=(child_title,),
            )
            # Also cache this citing paper
            child_key = (child_link, child_title)
            if child_key not in self.citations_cache:
                self.citations_cache[child_key] = citing_paper

        self.set_status(f"Found {len(citing_papers)} citing papers for: {title}")

    def set_status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = CitationExplorer()
    app.mainloop()

    # When you close the app, optionally quit the driver:
    app.driver.quit()
