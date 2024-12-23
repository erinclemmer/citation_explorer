import tkinter as tk
from tkinter import ttk, Toplevel, Listbox, END
import time

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService

###################################################
# Configure Selenium for Firefox
###################################################
FIREFOX_DRIVER_PATH = "C:\\Users\\alice\\Documents\\programs\\geckodriver.exe"

firefox_options = FirefoxOptions()
# firefox_options.add_argument("--headless")  # if you want headless mode

def init_driver():
    service = FirefoxService(executable_path=FIREFOX_DRIVER_PATH)
    driver = webdriver.Firefox(service=service, options=firefox_options)
    return driver

###################################################
# Google Scholar Helpers (Simplified)
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
            "next_page_url": None
        })

    # If there's a next link
    next_page_url = None
    try:
        next_button = driver.find_element(By.LINK_TEXT, "Next")
        next_page_url = next_button.get_attribute("href")
    except NoSuchElementException:
        pass

    if next_page_url:
        # Add a special "Load Next Page >>" item
        results.append({
            "title": "Load Next Page >>",
            "link": None,
            "cited_by_link": None,
            "is_next_page": True,
            "next_page_url": next_page_url
        })
    return results

def get_citing_papers(cited_by_url, driver, max_results=10, page_url=None):
    """ Similar to search_google_scholar, but for a 'cited by' page. """
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
            "next_page_url": None
        })

    # Check for "Next"
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
            "next_page_url": next_page_url
        })

    return results

###################################################
# Main Tkinter App
###################################################
class CitationExplorer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Google Scholar Citation Explorer (Fix Next Page Cache)")
        self.geometry("1100x600")

        self.driver = init_driver()
        self.citations_cache = {}

        # Controls
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Search Query:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(control_frame, textvariable=self.search_var, width=50)
        self.search_entry.pack(side=tk.LEFT, padx=5)

        search_button = ttk.Button(control_frame, text="Search", command=self.do_search)
        search_button.pack(side=tk.LEFT, padx=5)

        self.status_var = tk.StringVar(value="Enter a search query.")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Treeview
        self.tree = ttk.Treeview(self, columns=("title",), selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.heading("#0", text="Paper Link / Special", anchor=tk.W)
        self.tree.heading("title", text="Title", anchor=tk.W)

        self.tree.column("#0", width=450, stretch=False)
        self.tree.column("title", width=600, stretch=True)

        self.tree.bind("<Double-1>", self.on_tree_item_double_click)

    def do_search(self):
        query = self.search_var.get().strip()
        if not query:
            self.set_status("Please enter a query.")
            return

        self.set_status(f"Searching for: {query}")
        results = search_google_scholar(query, self.driver, max_results=10)
        if not results:
            self.set_status("No results found or parse error.")
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
                listbox.insert(END, f"[NEXT PAGE] {r['title']}")
            else:
                listbox.insert(END, r["title"])

        def on_select(event):
            selection = listbox.curselection()
            if not selection:
                return
            index = selection[0]
            paper = results[index]
            if paper["is_next_page"]:
                # Load next page
                next_res = search_google_scholar(
                    query=None,
                    driver=self.driver,
                    max_results=10,
                    page_url=paper["next_page_url"]
                )
                # Replace current results
                results.clear()
                results.extend(next_res)
                listbox.delete(0, END)
                for nr in next_res:
                    if nr["is_next_page"]:
                        listbox.insert(END, f"[NEXT PAGE] {nr['title']}")
                    else:
                        listbox.insert(END, nr["title"])
            else:
                popup.destroy()
                self.load_root_paper(paper)

        listbox.bind("<Double-1>", on_select)

    def load_root_paper(self, paper):
        self.tree.delete(*self.tree.get_children())
        self.citations_cache.clear()

        link = paper.get("link") or "(no link)"
        title = paper.get("title") or "(no title)"

        root_id = self.tree.insert(
            "", tk.END,
            text=link,
            values=(title,),
            open=True
        )
        # Insert in cache
        self.citations_cache[(link, title)] = paper

        self.expand_citations(root_id, paper)
        self.set_status(f"Loaded root: {title}")

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

        # If it's the special next-page item
        if paper.get("is_next_page", False):
            next_url = paper.get("next_page_url")
            if not next_url:
                return

            # Remove this "Load Next Page >>" node
            parent_id = self.tree.parent(item_id)
            self.tree.delete(item_id)

            # Now fetch the next page
            citing = get_citing_papers(None, self.driver, max_results=10, page_url=next_url)

            # The parent paper
            parent_link = self.tree.item(parent_id, "text")
            parent_title = self.tree.item(parent_id, "values")[0]
            parent_key = (parent_link, parent_title)
            parent_paper = self.citations_cache.get(parent_key, {})
            if "citing" not in parent_paper:
                parent_paper["citing"] = []
            parent_paper["citing"].extend(citing)

            # Insert them
            for c_paper in citing:
                self.insert_citing_node(parent_id, c_paper)

            self.set_status("Loaded next page of citing papers.")
        else:
            # If normal paper, expand if not already expanded
            children = self.tree.get_children(item_id)
            if children:
                self.set_status("Already expanded.")
                return
            self.expand_citations(item_id, paper)

    def expand_citations(self, parent_item_id, paper):
        link = paper.get("link")
        title = paper.get("title")
        if "citing" not in paper:
            # fetch them
            cb_url = paper.get("cited_by_link")
            if cb_url:
                self.set_status(f"Fetching citing papers for: {title}")
                citing = get_citing_papers(cb_url, self.driver, max_results=10)
                paper["citing"] = citing
            else:
                paper["citing"] = []
            self.citations_cache[(link, title)] = paper

        for c_paper in paper["citing"]:
            self.insert_citing_node(parent_item_id, c_paper)

        self.set_status(f"{len(paper['citing'])} citing papers for: {title}")

    def insert_citing_node(self, parent_item_id, c_paper):
        """
        Insert a child node for `c_paper`. If it's a "Load Next Page >>",
        we use text="[NEXT PAGE]" and values=("Load Next Page >>",).
        Otherwise, text=paper's link, values=paper's title.
        """
        if c_paper["is_next_page"]:
            text = "[NEXT PAGE]"
            val = "Load Next Page >>"
        else:
            text = c_paper.get("link") or ""
            val = c_paper.get("title") or ""

        child_id = self.tree.insert(
            parent_item_id,
            tk.END,
            text=text,
            values=(val,),
            open=False
        )
        # Store in cache under the same key
        self.citations_cache[(text, val)] = c_paper

    def set_status(self, msg):
        self.status_var.set(msg)
        self.update_idletasks()


if __name__ == "__main__":
    app = CitationExplorer()
    app.mainloop()
    app.driver.quit()
