# LocalFind 🏪

> Find your local shop in seconds

LocalFind is a hyperlocal shopping platform where users search for any item and nearby registered shops instantly respond on WhatsApp — including price quotes that are shown only to that specific user.

---

## 📸 Features

- 🔍 **Item Search** — user searches for anything, all shops within 5km get notified instantly
- 🔔 **Real-time WhatsApp Notification** — shops receive requests directly on WhatsApp
- 🔒 **Private Pricing** — the price a shop quotes is visible only to that user, not publicly
- 📱 **Dual WhatsApp Number** — shop can add 2 numbers; if one number replies first, the other automatically gets a "reply already sent" message
- 📍 **Location-based Filtering** — exact distance calculated using the Haversine formula
- ✅ **No App Needed** — WhatsApp is enough for both users and shopkeepers

---

Project Structure

```
localfind/
│
├── app.py                  # Flask server — main entry point
├── utils.py                # Auth, distance, validation helpers
├── requirements.txt        # Python dependencies
├── .env                    # Secret keys (never push to GitHub!)
│
├── db/
│   ├── __init__.py
│   └── schema.py           # SQLite database tables
│
├── routes/
│   ├── __init__.py
│   ├── shops.py            # Shop register, login, respond endpoints
│   └── requests.py         # User request, search, select endpoints
│
├── index.html              # Homepage
├── shop_register.html      # Shop registration form
└── search.html             # User search page
```

---

## ⚙️ Setup — Run on Local Machine

### 1. Install Python
Go to https://python.org/downloads — make sure to tick **"Add Python to PATH"**

### 2. Clone the project
```bash
git clone https://github.com/your-username/localfind.git
cd localfind
```

### 3. Install Flaskk
```bash
pip install flask
```

### 4. Create `.env` file
```
SECRET_KEY=your-secret-key-here
PORT=5000
```

### 5. Run the server
```bash
python app.py
```

### 6. Open in browser
```
http://localhost:5000
```

---

 API Endpoints

### Shop Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/shops/register` | Register a new shop |
| POST | `/api/shops/login` | Shop owner login |
| GET | `/api/shops/me` | Get your shop profile |
| PUT | `/api/shops/me` | Update shop profile |
| GET | `/api/shops/requests` | View nearby open requests |
| POST | `/api/shops/respond` | Reply to a request |
| GET | `/api/shops/responses` | View reply history |

### User Endpoints
| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/requests/new` | Send an item search request |
| GET | `/api/requests/:id` | Check request status |
| GET | `/api/requests/:id/responses` | View shop responses + prices |
| POST | `/api/requests/:id/select` | Choose a shop → get WhatsApp link |
| POST | `/api/requests/:id/cancel` | Cancel a request |

### Health Check
```
GET /api/health


---

## 📱 Dual WhatsApp Number — How It Works

```
User sends a request
        ↓
Both numbers receive notification
        ↓
Number 1 replies first ✅
        ↓
Bot sends message to Number 2:
"This order was already replied to from Number 1"
        ↓
Order locked — no duplicate reply possible
```

---

## 🗄️ Database Tables

| Table | Purpose |
|-------|---------|
| `shops` | Registered shops — location, WhatsApp numbers, details |
| `users` | Customers who search for items |
| `requests` | Item search requests from users |
| `responses` | Shop replies — price, availability, lock status |

---

## 🚀 Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python + Flask |
| Database | SQLite |
| Frontend | HTML, CSS, JavaScript |
| Auth | HMAC-based signed tokens |
| Distance | Haversine formula |
| WhatsApp | Twilio / Meta Cloud API (coming soon) |


## 🛣️ Roadmap

- [x] Shop registration with dual WhatsApp numbers
- [x] User item search with location radius
- [x] Private pricing system
- [x] Dual number lock logic
- [x] WhatsApp order link generation
- [ ] WhatsApp Bot integration (Twilio / Meta API)
- [ ] Shop dashboard
- [ ] Rating & review system
- [ ] SMS fallback



## 👨‍💻 Developer

Built with ❤️ for local businesses of India 🇮🇳

---

📄 License

MIT License — free to use, modify, and distribute.
