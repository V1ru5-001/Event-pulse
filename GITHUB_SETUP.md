# 🔗 How to Connect Your Project to GitHub

A step-by-step guide for pushing EventPulse to GitHub for the first time.

---

## STEP 1 — Install Git (if not already installed)

Open your terminal and check:
```bash
git --version
```

If you see a version number, you're good. If not, download Git from:
👉 https://git-scm.com/downloads

---

## STEP 2 — Configure Git with Your Identity

Tell Git who you are (do this once on your machine):
```bash
git config --global user.name "Your Name"
git config --global user.email "your@email.com"
```

---

## STEP 3 — Create a Repository on GitHub

1. Go to https://github.com
2. Click the **"+"** icon → **"New repository"**
3. Name it: `eventpulse`
4. Set it to **Private** (your code is not open source)
5. Do NOT check "Add README" — you already have one
6. Click **"Create repository"**

---

## STEP 4 — Initialise Git in Your Project Folder

Open your terminal, navigate to your EventPulse project folder:
```bash
cd path/to/your/eventpulse
```

Then initialise Git:
```bash
git init
```

---

## STEP 5 — Add Your Files

Stage all your files for the first commit:
```bash
git add .
```

Make your first commit:
```bash
git commit -m "Initial commit — EventPulse v0.1"
```

---

## STEP 6 — Connect to GitHub

Copy the repository URL from GitHub (looks like):
`https://github.com/yourusername/eventpulse.git`

Then connect your local project to it:
```bash
git remote add origin https://github.com/yourusername/eventpulse.git
```

---

## STEP 7 — Push to GitHub

```bash
git branch -M main
git push -u origin main
```

Your code is now on GitHub. ✅

---

## ⚡ Daily Workflow (After First Setup)

Every time you make changes and want to save them to GitHub:

```bash
# 1. Check what changed
git status

# 2. Stage your changes
git add .

# 3. Commit with a message describing what you did
git commit -m "Added event RSVP feature"

# 4. Push to GitHub
git push
```

---

## 🔐 Authentication — GitHub Personal Access Token

GitHub no longer accepts passwords. You need a **Personal Access Token (PAT)**:

1. Go to GitHub → Settings → Developer Settings
2. Click **Personal Access Tokens** → **Tokens (classic)**
3. Click **Generate new token**
4. Give it a name: `eventpulse-dev`
5. Set expiration: 90 days
6. Check **repo** scope
7. Click **Generate token**
8. **Copy it immediately** — you won't see it again

When Git asks for your password, paste this token instead.

---

## 💡 Useful Git Commands

```bash
# See all your commits
git log --oneline

# Undo last commit (keeps your changes)
git reset --soft HEAD~1

# See what branch you're on
git branch

# Create a new branch (for new features)
git checkout -b feature/rsvp-system

# Switch back to main
git checkout main
```

---

## ⚠️ IMPORTANT — What Never Goes to GitHub

Your `.gitignore` already handles this, but always double-check:

- ❌ `.env` file — contains your secret key
- ❌ `db.sqlite3` — your local database
- ❌ `venv/` — your virtual environment
- ❌ `media/` — uploaded images

These are already in your `.gitignore`. You're safe. ✅
