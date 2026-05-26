# Panini Tracker 🏆

> Track your FIFA World Cup 2026 Panini sticker collection 
> using AI-powered photo detection from your iPhone.

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.12-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)

## ✨ Features

- 📸 **Scan album pages** — photograph a team's double page 
  spread from your iPhone and detect missing vs owned stickers
- 🤖 **AI detection** — Groq Vision (llama-4-scout) analyzes 
  each page and pre-fills the review screen
- ✅ **Review & confirm** — review all 20 slots with toggle 
  cards before saving. Use "All Missing" for quick setup
- 🌍 **980 stickers** — complete catalog for 48 teams 
  pre-loaded from Panini FIFA WC 2026
- 📖 **Album page numbers** — each team shows its album 
  page number for easy navigation
- 🔄 **Swap management** — track duplicates, adjust quantities 
  and share your swap list via WhatsApp
- 📊 **Stats & progress** — completion tracking by team 
  with progress bars and percentages
- ✨ **Special stickers** — manual tracking for FWC, 
  Coca-Cola Europe and Host Cities special stickers
- 🏳️ **48 teams** — all qualified nations with flag emojis 
  and country filters
- 📱 **Mobile-first** — designed for iPhone browser on 
  local network, works on any device

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | HTML + CSS + Vanilla JavaScript |
| Database | SQLite |
| AI Vision | Groq API (llama-4-scout-17b) |
| Image Processing | OpenCV + Pillow |
| Catalog Scraping | BeautifulSoup4 |

## 🚀 Quick Start

### Requirements
- Python 3.12+
- [Groq API key](https://console.groq.com) — free tier, 
  no credit card needed

### Installation

```bash
git clone https://github.com/LtVerdugo/panini-sticker-album-tracker
cd panini-sticker-album-tracker

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

### 📱 iPhone Access

```bash
ipconfig getifaddr en0  # Get your local IP
```

Open **http://YOUR_LOCAL_IP:8000** in Safari or Chrome
on your iPhone. Must be on the same WiFi network.

## 📁 Project Structure

```
panini-sticker-album-tracker/
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
│   └── sticker_catalog_full.csv  # 980 stickers catalog
├── tools/
│   ├── scrape_catalog.py    # Scrape catalog from web
│   └── add_team_to_catalog.py    # Add team manually
├── .env.example             # Environment variables template
├── requirements.txt
├── LICENSE
└── README.md
```

## 🔌 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /scan | Analyze album page photo with AI |
| POST | /confirm | Save confirmed sticker status |
| POST | /sticker/{id}/decrement | Decrease sticker quantity |
| GET | /collection | Get owned stickers |
| GET | /missing | Get missing stickers |
| GET | /duplicates | Get duplicate stickers |
| GET | /stats | Get collection statistics |
| POST | /catalog/import/full | Import full catalog CSV |

## 📖 How to Use

### Scanning Album Pages
1. Open the app on your iPhone browser
2. Tap the red camera button in the center
3. Select AI Detection
4. Photograph the album page horizontally 
   with good lighting
5. Tap **Analyze Page**

### Reviewing Results
6. Review the 20 toggle cards
7. Tap **All Missing** then tap only the 
   stickers you own
8. Tap **Confirm & Save**

### Special Stickers (FWC, Coca-Cola)
- Go to **Missing → Special Stickers** section
- Tap any special sticker you have
- Tap **I got this sticker!**

### Managing Duplicates
- Go to **Swap** tab
- Use **+** / **−** buttons to adjust quantities
- Tap **Share Swap List** to send via WhatsApp

## 🗺 Album Page Index

All 48 teams with their album page numbers:

| Page | Code | Team |
|------|------|------|
| 8 | MEX | Mexico |
| 10 | RSA | South Africa |
| 12 | KOR | Korea Republic |
| 14 | CZE | Czechia |
| 16 | CAN | Canada |
| 18 | BIH | Bosnia-Herzegovina |
| 20 | QAT | Qatar |
| 22 | SUI | Switzerland |
| 24 | BRA | Brazil |
| 26 | MAR | Morocco |
| 28 | HAI | Haiti |
| 30 | SCO | Scotland |
| 32 | USA | USA |
| 34 | PAR | Paraguay |
| 36 | AUS | Australia |
| 38 | TUR | Türkiye |
| 40 | GER | Germany |
| 42 | CUW | Curaçao |
| 44 | CIV | Côte d'Ivoire |
| 46 | ECU | Ecuador |
| 48 | NED | Netherlands |
| 50 | JPN | Japan |
| 52 | SWE | Sweden |
| 54 | TUN | Tunisia |
| 58 | BEL | Belgium |
| 60 | EGV | Egypt |
| 62 | IRN | IR Iran |
| 64 | NZL | New Zealand |
| 66 | ESP | Spain |
| 68 | CPV | Cabo Verde |
| 70 | KSA | Saudi Arabia |
| 72 | URU | Uruguay |
| 74 | FRA | France |
| 76 | SEN | Senegal |
| 78 | IRQ | Iraq |
| 80 | NOR | Norway |
| 82 | ARG | Argentina |
| 84 | ALG | Algeria |
| 86 | AUT | Austria |
| 88 | JOR | Jordan |
| 90 | POR | Portugal |
| 92 | COD | Congo DR |
| 94 | UZB | Uzbekistan |
| 96 | COL | Colombia |
| 98 | ENG | England |
| 100 | CRO | Croatia |
| 102 | GHA | Ghana |
| 104 | PAN | Panama |

## 🌱 Roadmap

- [ ] Better AI vision model for improved detection
- [ ] PWA support — installable on iPhone home screen
- [ ] Google Sheets sync for collection sharing
- [ ] Barcode scanning for individual stickers
- [ ] Multi-album support

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

## 🙏 Credits

- Sticker catalog data from 
  [laststicker.com](https://www.laststicker.com)
- AI vision powered by [Groq](https://groq.com)
- Built with [FastAPI](https://fastapi.tiangolo.com)
