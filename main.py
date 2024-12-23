import tkinter as tk
from tkinter import ttk
import requests

# -----------------------------------
# Configuration
# -----------------------------------
API_URL = "https://api.semanticscholar.org/graph/v1"
API_KEY = "YOUR_API_KEY_HERE"
# Adjust these fields as you wish:
ROOT_FIELDS = "title,year"              # to retrieve metadata of the root paper
CITATION_FIELDS = "title,year,citations"  # fields for citing papers
DEFAULT_PAGE_SIZE = 50                  # how many citations to load per call

# -----------------------------------
# API Helper Functions
# -----------------------------------
def fetch_paper_info(paper_id, fields=ROOT_FIELDS):
    """
    Fetch metadata for a single paper (e.g., title, year).
    Returns a dict with keys like 'paperId', 'title', 'year', 'citations', etc.
    If there's an error, returns None.
    """
    # headers = {"x-api-key": API_KEY}
    headers = { }
    url = f"{API_URL}/paper/{paper_id}?fields={fields}"
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching paper info: {e}")
        return None

def get_forward_citations(paper_id, limit=DEFAULT_PAGE_SIZE, offset=0):
    """
    Fetch the papers that cite the given paper (forward citations).
    Returns (citations_list, total_citations_count) or ([], 0) on error.
    
    The Graph API endpoint:
      GET /paper/{paper_id}?fields=title,year,citations
    By default, up to 100 citing papers can be returned. 
    If you need more, you can handle 'offset' and 'limit'.
    """
    # headers = {"x-api-key": API_KEY}
    headers = { }
    
    # We include 'citations.paperId', 'citations.title', etc. in CITATION_FIELDS
    url = (
        f"{API_URL}/paper/{paper_id}"
        f"?fields={CITATION_FIELDS}&limit={limit}&offset={offset}"
    )
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        
        # The top-level paper is returned in 'data', with a 'citations' field
        citations = data.get("citations", [])
        
        # The total number of citing papers might be found in 'data["citationCount"]'
        # but it’s not always accurate. Alternatively, you can parse the "next" link
        # from the "links" field if the API returns it. For simplicity, let's assume
        # the total is the length of the citations array plus offset. 
        total_citations = data.get("citationCount", len(citations))
        return citations, total_citations
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching citations for {paper_id}: {e}")
        return [], 0

# -----------------------------------
# Main Tkinter App
# -----------------------------------
class CitationExplorer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Semantic Scholar Citation Explorer")
        self.geometry("900x600")

        # Caches to avoid repeated calls for the same paper
        #   citations_cache[paper_id] = list of citations already fetched
        self.citations_cache = {}

        # Create frames
        control_frame = ttk.Frame(self)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Paper ID entry
        ttk.Label(control_frame, text="Enter Paper ID/DOI/ArXiv:").pack(side=tk.LEFT, padx=5)
        self.paper_id_var = tk.StringVar()
        self.paper_id_entry = ttk.Entry(control_frame, textvariable=self.paper_id_var, width=50)
        self.paper_id_entry.pack(side=tk.LEFT, padx=5)

        load_button = ttk.Button(control_frame, text="Load", command=self.load_root_paper)
        load_button.pack(side=tk.LEFT, padx=5)

        # Status label
        self.status_var = tk.StringVar(value="Waiting for input...")
        self.status_label = ttk.Label(control_frame, textvariable=self.status_var, foreground="blue")
        self.status_label.pack(side=tk.LEFT, padx=10)

        # Treeview
        self.tree = ttk.Treeview(self, columns=("title", "year"), selectmode="browse")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Define columns & headings
        self.tree.heading("#0", text="Paper ID", anchor=tk.W)
        self.tree.heading("title", text="Title", anchor=tk.W)
        self.tree.heading("year", text="Year", anchor=tk.CENTER)

        self.tree.column("#0", width=220, stretch=False)
        self.tree.column("title", width=500, stretch=True)
        self.tree.column("year", width=60, stretch=False, anchor=tk.CENTER)

        # Bind double-click
        self.tree.bind("<Double-1>", self.on_tree_item_double_click)

    def load_root_paper(self):
        """
        Clears the tree and loads the top-level paper. 
        Then fetches its forward citations.
        """
        paper_id = self.paper_id_var.get().strip()
        if not paper_id:
            self.set_status("Please enter a valid paper ID/DOI/ArXiv.")
            return

        # Clear existing tree & caches
        self.tree.delete(*self.tree.get_children())
        self.citations_cache.clear()

        # Get the root paper’s metadata
        self.set_status(f"Fetching metadata for {paper_id}...")
        paper_info = fetch_paper_info(paper_id)
        if not paper_info:
            self.set_status("Failed to fetch the root paper. Check the ID or your connection.")
            return

        # Create the root node
        root_title = paper_info.get("title", "(Unknown Title)")
        root_year = paper_info.get("year", "")
        root_node = self.tree.insert(
            "",
            tk.END,
            text=paper_id,  # paper ID in the leftmost column
            values=(root_title, root_year),
            open=True
        )

        # Preemptively fetch and attach its forward citations
        self.expand_citations(root_node, paper_id)
        self.set_status("Root paper loaded.")

    def on_tree_item_double_click(self, event):
        """
        Expand the citations for a node if not already expanded/cached.
        """
        item_id = self.tree.focus()
        if not item_id:
            return

        # If it already has children, we assume it's expanded or partially loaded.
        # You could handle "Load More" logic here if you want to page further results.
        children = self.tree.get_children(item_id)
        if children:
            self.set_status("Already expanded.")
            return

        # Get the paper ID from the node
        paper_id = self.tree.item(item_id, "text")
        self.expand_citations(item_id, paper_id)

    def expand_citations(self, parent_item_id, paper_id):
        """
        Fetch forward citations of `paper_id` (unless cached),
        and insert them as children under the node `parent_item_id`.
        """
        # Check cache
        if paper_id in self.citations_cache:
            citations = self.citations_cache[paper_id]
        else:
            self.set_status(f"Fetching citations for {paper_id}...")
            citations, total = get_forward_citations(paper_id, limit=DEFAULT_PAGE_SIZE, offset=0)
            self.citations_cache[paper_id] = citations  # store in cache

        for c in citations:
            child_id = c.get("paperId")
            title = c.get("title", "Unknown Title")
            year = c.get("year", "")

            # Avoid inserting duplicates if they exist
            if not self._child_exists(parent_item_id, child_id):
                self.tree.insert(parent_item_id, tk.END, text=child_id, values=(title, year))

        self.set_status(f"Found {len(citations)} citing papers for {paper_id}.")

    def _child_exists(self, parent_item_id, child_paper_id):
        """
        Check if a child with the given paperId is already present 
        under the specified parent in the Treeview.
        """
        for child_id in self.tree.get_children(parent_item_id):
            existing_text = self.tree.item(child_id, "text")
            if existing_text == child_paper_id:
                return True
        return False

    def set_status(self, message):
        """ Update status label text. """
        self.status_var.set(message)


if __name__ == "__main__":
    app = CitationExplorer()
    app.mainloop()
