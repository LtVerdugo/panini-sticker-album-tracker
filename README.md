# Panini Tracker 🏆

> Track your FIFA World Cup 2026 Panini sticker collection 
> using AI-powered photo detection from your iPhone.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)

## ✨ Features

- 📸 **Scan album pages** — photograph a team's double page 
  spread from your iPhone
- 🤖 **AI detection** — Groq Vision detects missing vs owned 
  stickers automatically
- ✅ **Review & confirm** — review all 20 slots before saving
- 🌍 **940 stickers** — complete catalog for 48 teams 
  pre-loaded from Panini WC 2026
- 🔄 **Swap management** — track duplicates and share 
  your swap list via WhatsApp
- 📊 **Stats & progress** — completion tracking by team
- ✨ **Special stickers** — manual tracking for FWC and 
  Coca-Cola special stickers
- 📱 **Mobile-first** — works from iPhone browser on 
  local network

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | HTML + CSS + Vanilla JavaScript |
| Database | SQLite |
| AI Vision | Groq API (llama-4-scout) |
| Image Processing | OpenCV + Pillow |

## 🚀 Quick Start

### Requirements
- Python 3.12+
- [Groq API key](https://console.groq.com) (free)

### Installation

```bash
git clone https://github.com/YOUR_USERNAME/panini-tracker
cd panini-tracker

# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### Run

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

### 📱 Mobile Access (iPhone)

```bash
ipconfig getifaddr en0  # Get your local IP
```

Open **http://YOUR_LOCAL_IP:8000** in Safari or Chrome 
on your iPhone (must be on same WiFi network).

## 📁 Project Structure

```
panini_camera_tracker/
├── api/
│   └── main.py              # FastAPI backend + all endpoints
├── frontend/
│   ├── index.html           # App shell + navigation
│   ├── style.css            # All styles (mobile-first)
│   └── app.js               # Frontend logic + API calls
├── src/
│   ├── database.py          # SQLite operations
│   └── collection_service.py # Collection business logic
├── data/
│   ├── sticker_catalog_full.csv  # 940 stickers catalog
│   └── sticker_catalog.csv       # Legacy catalog
├── tools/
│   ├── scrape_catalog.py    # Scrape catalog from web
│   └── add_team_to_catalog.py    # Add team manually
├── .env.example             # Environment template
└── requirements.txt
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /scan | Analyze album page photo |
| POST | /confirm | Save confirmed sticker status |
| GET | /collection | Get owned stickers |
| GET | /missing | Get missing stickers |
| GET | /duplicates | Get duplicate stickers |
| GET | /stats | Get collection statistics |
| POST | /catalog/import/full | Import full catalog CSV |

## 📖 How to Use

1. **Open the app** on your iPhone browser
2. **Tap the red camera button** to scan a page
3. **Select AI Detection** and photograph the album page 
   horizontally
4. **Review the 20 slots** — use "All Missing" then tap 
   what you own
5. **Confirm & Save** — your collection updates instantly
6. **Special stickers** (FWC, Coca-Cola) — go to 
   Missing → Special Stickers and mark manually

## 🌱 Roadmap

- [ ] Better AI model for sticker detection
- [ ] PWA support (installable on iPhone)
- [ ] Google Sheets sync
- [ ] Barcode scanning for individual stickers
- [ ] Multi-album support

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Credits

- Sticker catalog data from 
  [laststicker.com](https://www.laststicker.com)
- AI vision powered by [Groq](https://groq.com)
