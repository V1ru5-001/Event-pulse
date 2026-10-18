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

## 🚢 Deploying

EventPulse runs on Vercel with a Supabase Postgres database and Supabase Storage (S3-compatible) for uploads.

**Environment variables** (set in Vercel → Settings → Environment Variables; never commit them):

| Name | Notes |
|---|---|
| `SECRET_KEY` | Long random string. Required in production. |
| `DEBUG` | Leave unset (or `False`) in production. |
| `DATABASE_URL` | Supabase Postgres connection string. Write special characters in the password URL-encoded (`@` → `%40`). |
| `ALLOWED_HOSTS` | Optional, comma-separated. `.vercel.app` is always allowed. |
| `CSRF_TRUSTED_ORIGINS` | Optional, comma-separated. Defaults to `https://*.vercel.app`; add your custom domain here. |
| `USE_S3` | `True` to store uploads in Supabase Storage. |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Supabase Storage S3 access keys. |
| `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_S3_ENDPOINT_URL` | Bucket name, region and Supabase S3 endpoint. |
| `AWS_S3_CUSTOM_DOMAIN` | Optional public domain for uploaded files. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Google OAuth client. Without both, the "Continue with Google" buttons are hidden. |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL` | SMTP for sign-up codes and password resets. Required in production: without them new users can't verify their email. Locally, with `DEBUG=True` and no `EMAIL_HOST`, emails print to the console. |
| `TRUST_X_FORWARDED_FOR` | Optional. Not needed on Vercel (it's trusted automatically there via `VERCEL=1`); set `True` only behind another proxy that overwrites `X-Forwarded-For`. |
| `SENTRY_DSN` | Optional. Turns on Sentry error tracking (no personal data, request bodies or cookies are sent). Leave unset to disable. |
| `SENTRY_ENVIRONMENT` | Optional label shown in Sentry. Defaults to `production`. |

**Migrations:** Vercel does not run `migrate`. After every push that adds a migration, run it against Supabase from your machine:

```powershell
$env:DATABASE_URL = "<your Supabase connection string>"
python manage.py migrate
Remove-Item Env:DATABASE_URL
```

Until you do, pages that use the new tables or columns will return a 500 error.

### Email troubleshooting

Sign-up codes and password resets are sent over SMTP using these env vars (names only):
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS` (port 587, the default) or `EMAIL_USE_SSL` (port 465),
`EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`.

To test a configuration step by step (it never prints the password), set the same env vars locally and run:

```powershell
python manage.py test_email you@example.com
```

It shows each step (connect, EHLO, STARTTLS, login, send) as OK or FAIL, with the server's exact reply.
Failed sends are logged on Vercel as `Could not send … to a***@domain: <ErrorType>: <message>`.

If you're locked out while testing, clear the rate-limit counters in the Supabase SQL editor:
`delete from accounts_auththrottle;`

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
