import csv
import json
import sqlite3
import threading
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk

try:
    import docx
except ImportError:
    docx = None
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

DB_PATH = Path("secure_index.sqlite3")
CONFIG_PATH = Path("secure_search_config.json")
SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".pdf", ".docx"}

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def load_config():
    if CONFIG_PATH.is_file():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"last_folder": "", "dark_mode": True}

def save_config(folder_path, dark_mode):
    try:
        data = {"last_folder": str(folder_path), "dark_mode": bool(dark_mode)}
        CONFIG_PATH.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass

def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return ""
    if ext in {".txt", ".md"}:
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    if ext == ".docx":
        if docx is None:
            return "[Error: python-docx missing]"
        try:
            return "\n".join([p.text for p in docx.Document(path).paragraphs])
        except Exception:
            return ""
    if ext == ".pdf":
        if PdfReader is None:
            return "[Error: pypdf missing]"
        try:
            r = PdfReader(path)
            return "\n".join([pg.extract_text() for pg in r.pages if pg.extract_text()])
        except Exception:
            return ""
    if ext == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return ""
        parts = []
        def walk(v):
            if isinstance(v, str):
                parts.append(v)
            elif isinstance(v, dict):
                for x in v.values():
                    walk(x)
            elif isinstance(v, list):
                for x in v:
                    walk(x)
        walk(data)
        return "\n".join(parts)
    return ""

def connect_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("CREATE VIRTUAL TABLE IF NOT EXISTS documents USING fts5(path UNINDEXED, content)")
    return db

def clean_fts_query(raw_query: str) -> str:
    clean = "".join(c if c.isalnum() or c.isspace() else " " for c in raw_query)
    return " AND ".join(f"{word}*" for word in clean.split() if word)

def db_search(query: str, limit=200):
    db = connect_db()
    safe_query = clean_fts_query(query)
    if not safe_query:
        return
    try:
        return db.execute("SELECT path, snippet(documents, -1, '[[\x27, \x27]]', ' … ', 40) FROM documents WHERE documents MATCH ? ORDER BY rank LIMIT ?", (safe_query, limit)).fetchall()
    except Exception:
        return
    finally:
        db.close()

def index_folder_worker(folder, dark_mode_bool, callback_done, callback_error):
    def run():
        try:
            db = connect_db()
            db.execute("DELETE FROM documents")
            count = 0
            for path in Path(folder).rglob("*"):
                if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    text = extract_text(path)
                    if text.strip():
                        db.execute("INSERT INTO documents (path, content) VALUES (?, ?)", (str(path), text))
                        count += 1
            db.commit()
            db.close()
            save_config(folder, dark_mode_bool())
            callback_done(count)
        except Exception as e:
            callback_error(e)
    threading.Thread(target=run, daemon=True).start()

class ModernSearchApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CoLocate - Private Local Indexing Vault")
        self.geometry("1100x700")
        self.minsize(900, 550)
        self.config = load_config()
        self.folder_var = ctk.StringVar(value=self.config.get("last_folder", ""))
        self.query_var = ctk.StringVar()
        self.status_var = ctk.StringVar(value="Ready. Choose a repository.")
        self.results_data = []

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.top_frame = ctk.CTkFrame(self, corner_radius=12)
        self.top_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.lbl_folder = ctk.CTkLabel(self.top_frame, text="Repository:", font=("Segoe UI", 12, "bold"))
        self.lbl_folder.grid(row=0, column=0, padx=15, pady=15, sticky="w")
        self.entry_folder = ctk.CTkEntry(self.top_frame, textvariable=self.folder_var, font=("Segoe UI", 12))
        self.entry_folder.grid(row=0, column=1, padx=10, pady=15, sticky="ew")
        self.btn_browse = ctk.CTkButton(self.top_frame, text="Browse Folder", width=120, command=self.choose_folder)
        self.btn_browse.grid(row=0, column=2, padx=5, pady=15)
        self.btn_index = ctk.CTkButton(self.top_frame, text="Build Index", width=140, fg_color="#1f93ff", hover_color="#0069cb", font=("Segoe UI", 12, "bold"), command=self.trigger_index)
        self.btn_index.grid(row=0, column=3, padx=15, pady=15)

        self.lbl_query = ctk.CTkLabel(self.top_frame, text="Keywords:", font=("Segoe UI", 12, "bold"))
        self.lbl_query.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="w")
        self.entry_query = ctk.CTkEntry(self.top_frame, textvariable=self.query_var, placeholder_text="Enter search terms...", font=("Segoe UI", 12))
        self.entry_query.grid(row=1, column=1, padx=10, pady=(0, 15), sticky="ew")
        self.entry_query.bind("<Return>", self.execute_search)
        self.btn_search = ctk.CTkButton(self.top_frame, text="Search", width=120, command=self.execute_search)
        self.btn_search.grid(row=1, column=2, padx=5, pady=(0, 15))
        self.btn_export = ctk.CTkButton(self.top_frame, text="Export CSV", width=140, state="disabled", fg_color="#2eb85c", hover_color="#1b853e", command=self.export_results)
        self.btn_export.grid(row=1, column=3, padx=15, pady=(0, 15))

        self.progress_bar = ctk.CTkProgressBar(self.top_frame, orientation="horizontal", height=6)

        self.main_split = ctk.CTkFrame(self, fg_color="transparent")
        self.main_split.grid(row=1, column=0, sticky="nsew", padx=20, pady=10)
        self.main_split.grid_rowconfigure(0, weight=1)
        self.main_split.grid_columnconfigure(1, weight=1)

        self.list_frame = ctk.CTkFrame(self.main_split, width=280)
        self.list_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.list_frame.grid_rowconfigure(1, weight=1)
        self.list_frame.grid_columnconfigure(0, weight=1)

        self.lbl_list_title = ctk.CTkLabel(self.list_frame, text="Matching Files", font=("Segoe UI", 12, "bold"))
        self.lbl_list_title.grid(row=0, column=0, padx=10, pady=10, sticky="w")
        self.file_listbox = tk.Listbox(self.list_frame, bd=0, highlightthickness=0, bg="#2b2b2b", fg="#dce4ee", selectbackground="#1f93ff", selectforeground="#ffffff", font=("Segoe UI", 10))
        self.file_listbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.file_listbox.bind("<<ListboxSelect>>", self.display_selected_file)

        self.text_frame = ctk.CTkFrame(self.main_split)
        self.text_frame.grid(row=0, column=1, sticky="nsew")
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)

        self.text_inspector = tk.Text(self.text_frame, wrap="word", bd=0, highlightthickness=0, bg="#232323", fg="#eceff4", insertbackground="#ffffff", padx=15, pady=15, font=("Consolas", 11))
        self.text_inspector.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        self.text_inspector.tag_configure("HIGHLIGHT", background="#e6c229", foreground="#121212")
        self.scrollbar = ctk.CTkScrollbar(self.text_frame, command=self.text_inspector.yview)
        self.scrollbar.grid(row=0, column=1, sticky="ns", pady=12, padx=(0, 12))
        self.text_inspector.config(yscrollcommand=self.scrollbar.set)

        self.footer = ctk.CTkFrame(self, height=32, corner_radius=0)
        self.footer.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.status_label = ctk.CTkLabel(self.footer, textvariable=self.status_var, font=("Segoe UI", 11))
        self.status_label.pack(side="left", padx=20, pady=4)

    def choose_folder(self):
        f = filedialog.askdirectory()
        if f:
            self.folder_var.set(f)
            save_config(f, True)

    def trigger_index(self):
        f = self.folder_var.get().strip()
        if not f or not Path(f).is_dir():
            messagebox.showwarning("Warning", "Please select a valid folder path.")
            return
        self.btn_index.configure(state="disabled")
        self.progress_bar.grid(row=2, column=0, columnspan=4, sticky="ew", padx=15, pady=(0, 10))
        self.progress_bar.set(0)
        self.progress_bar.start()
        self.status_var.set("Indexing documents...")
        index_folder_worker(f, lambda: True, self.on_index_complete, self.on_index_failure)

    def on_index_complete(self, count):
        self.progress_bar.stop()
        self.progress_bar.grid_forget()
        self.btn_index.configure(state="normal")
        self.status_var.set(f"Indexed {count} items.")
        messagebox.showinfo("Success", f"Indexed {count} assets successfully.")

    def on_index_failure(self, error):
        self.progress_bar.stop()
        self.progress_bar.grid_forget()
        self.btn_index.configure(state="normal")
        self.status_var.set("Index failed.")
        messagebox.showerror("Error", f"Exception raised:\n{str(error)}")

    def execute_search(self, event=None):
        q = self.query_var.get().strip()
        if not q:
            return
        self.file_listbox.delete(0, "end")
        self.text_inspector.config(state="normal")
        self.text_inspector.delete("1.0", "end")
        self.results_data.clear()
        try:
            hits = db_search(q)
            if hits:
                self.results_data.extend(hits)
        except Exception as e:
            messagebox.showerror("Query Error", str(e))
            return
        for p, esc in self.results_data:
            self.file_listbox.insert("end", Path(p).name)
        if self.results_data:
            self.file_listbox.selection_set(0)
            self.display_selected_file()
            self.status_var.set(f"Identified {len(self.results_data)} document traces.")
            self.btn_export.configure(state="normal")
        else:
            self.text_inspector.insert("end", "Zero matches found.")
            self.text_inspector.config(state="disabled")
            self.status_var.set("No matches identified.")
            self.btn_export.configure(state="disabled")

    def display_selected_file(self, event=None):
        sel = self.file_listbox.curselection()
        if not sel:
            return
        selected_index = list(sel).pop()
        matched_row = self.results_data[selected_index]
        path_str = list(matched_row).pop(0)

        content = extract_text(Path(path_str))
        self.text_inspector.config(state="normal")
        self.text_inspector.delete("1.0", "end")
        self.text_inspector.insert("end", f"SYSTEM PATH: {path_str}\n{'='*70}\n\n{content}")
        q = self.query_var.get().strip()
        if q:
            sp = "1.0"
            while True:
                sp = self.text_inspector.search(q, sp, stopindex="end", nocase=True)
                if not sp:
                    break
                ep = f"{sp}+{len(q)}c"
                self.text_inspector.tag_add("HIGHLIGHT", sp, ep)
                sp = ep
        self.text_inspector.config(state="disabled")

    def export_results(self):
        if not self.results_data:
            return
        sp = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Reports", "*.csv")])
        if not sp:
            return
        try:
            with open(sp, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Storage Path", "Snippet Context"])
                for path, snippet in self.results_data:
                    w.writerow([path, snippet.replace("[[", "").replace("]]", "")])
            messagebox.showinfo("Success", f"Data saved to:\n{sp}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

if __name__ == "__main__":
    app = ModernSearchApp()
    app.mainloop()
