# CoLocate v1.0.0 — Official User Manual

CoLocate is a high-performance, 100% offline personal indexing engine and text search utility designed for absolute data privacy. It allows you to ingest massive folders of raw files, AI chat logs, source repositories, PDFs, and Word documents into a secure local database, making your entire historical knowledge base instantly searchable without ever uploading a single byte to the cloud.

---

## 🛡️ Key Features
*   **Total Data Privacy:** Runs completely local on your hardware. Zero network connectivity or telemetry required.
*   **Multi-Format Ingestion:** Instantly parse and slice `.txt`, `.md`, `.json`, `.pdf`, and `.docx` file formats.
*   **Blazing-Fast Search:** Powered by a highly optimized SQLite3 FTS5 indexing framework for near-instant memory recall.
*   **Smart Highlighting:** Automatic syntax match highlighting loops reveal your exact target text snippets immediately.
*   **Zero CPU Lag:** Offloads processing weight away from production servers directly onto your client desktop interface.

---

## 🛠️ Setup

### 1. Clone the Repository
```bash
git clone https://github.com
cd CoLocate
```

### 2. Install Required Dependencies
Ensure you have Python 3.10+ installed on your system. Install the required data parsing and UI rendering engines:
```bash
pip install customtkinter pypdf python-docx
```

### 3. Run the Application
Launch the graphical interface raw using your system interpreter:
```bash
python3 app.py
```

---

## ⚙️ How to Use
1.  Launch **CoLocate** on your system.
2.  Click **Browse Folder** and select the target directory containing your text logs, source code, or AI conversation history archive dumps.
3.  Click **Build Index**. The background processing worker thread will build your secure localized search schema (`secure_index.sqlite3`).
4.  Type your target keyword parameters into the search input engine and press **Enter**.
5.  Select any identified file trace from the navigation layout panel matrix to preview the complete raw history with highlighted keywords.
