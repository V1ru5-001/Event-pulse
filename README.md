# EventPulse 🎉

> The campus event discovery platform built for Nigerian university students.

EventPulse is a two-sided marketplace connecting students who want to find campus events with organisers who want to reach campus audiences. Built for deep penetration on a single campus before expanding.

---

## 🚀 What It Does

- Students discover, save, and RSVP to campus events
- Organisers create, promote, and manage their events
- A freemium model rewards engaged users with powerful premium tools

---

## 💎 Pricing Tiers

| Tier | Price | For |
|---|---|---|
| Free | ₦0/month | Any student exploring campus |
| Student Premium | ₦1,500/month | Students who want the full experience |
| Organiser Premium | ₦3,500/month | Clubs, societies & event creators |
| Pulse Bundle | ₦4,500/month | Students who are also organisers |

---

## 🛠 Tech Stack

- **Backend:** Django 4.x (Python)
- **Database:** SQLite (development) / PostgreSQL (production)
- **Frontend:** HTML, CSS, JavaScript, Three.js
- **Payments:** Paystack / Flutterwave (coming soon)
- **Hosting:** TBD

---

## 📁 Project Structure

```
eventpulse/
├── accounts/        # User auth, profiles, plan management
├── events/          # Event creation, listing, detail pages
├── payments/        # Subscription plans, payment processing
├── dashboard/       # User & organiser dashboards
├── templates/       # All HTML templates
├── static/          # CSS, JS, images
├── eventpulse/      # Project settings and URLs
├── manage.py
├── requirements.txt
└── .gitignore
```

---

## ⚙️ Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/eventpulse.git
cd eventpulse
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
Create a `.env` file in the root directory:
```
SECRET_KEY=your-secret-key-here
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Seed initial data (categories, plans)
```bash
python manage.py seed_categories
```

### 7. Start the development server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000` in your browser.

---

## 🌟 Key Features

### For Students
- Personalised "For You" campus feed
- "Who's Going" — see friends attending events
- Squad Sync — group RSVP notifications
- Personal Campus Calendar with Conflict Detector
- AI Event Assistant

### For Organisers
- AI-powered event creation
- Featured placement & verified badge
- Full RSVP & attendee management
- Waitlist management
- Ghost Mode — stealth posts for premium students

---

## 🗺 Roadmap

- [x] Landing page & auth system
- [x] Event creation & detail pages
- [x] Pricing & plans page
- [ ] RSVP & Who's Going system
- [ ] Live Pulse Feed
- [ ] Paystack/Flutterwave integration
- [ ] AI Event Assistant
- [ ] Campus Hype Map
- [ ] Mobile app

---

## 👤 Author

**Virus** — Solo Founder, EventPulse  
Built in Awka, Nigeria 🇳🇬

---

## 📄 License

This project is private and not open source. All rights reserved.
