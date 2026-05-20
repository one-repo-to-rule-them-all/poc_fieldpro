# How This Whole Thing Works — Explained Like You're 14

This document explains what we built and what each tool does, in everyday words. No jargon (or when there is, we explain it).

If you've ever wondered "what does it actually mean to deploy a website?", this is for you.

---

## 1. What did we even build?

We built a **demo of a software product called FieldPro**. FieldPro is a tool for businesses that send crews out to job sites — think janitorial services, landscapers, equipment repair companies. They use it to keep track of:

- Their clients (the customers they work for)
- Their job sites (the actual buildings/parks they clean or maintain)
- Their crews (the people they send out)
- Work orders (the actual jobs to do — "clean the lobby on Friday")
- Invoices (the bills they send to clients)

The **demo** is a working version of this product, sitting on the internet, anyone can log in and try it. It's not connected to any real customer's data — it has fake data made up for the demo.

The demo lives at **https://fieldpro-poc.fly.dev**. The "backend" (the brains) lives at **https://fieldpro-poc-backend.fly.dev**.

---

## 2. How does it work at a high level?

Imagine a restaurant.

- **The frontend** is the dining room — what you see, the menu, the tables, where you place your order. (For us, this is the website.)
- **The backend** is the kitchen — where the food actually gets cooked, where the recipes are stored, where decisions are made. You never see the kitchen as a customer, but everything you eat comes from there.
- **The database** is the giant filing cabinet in the kitchen — every recipe, every customer order from the last year, every employee's schedule.
- **Redis** is the sticky notes on the kitchen wall — quick info the cooks need right now, fast to grab, but not permanent.

When you click "Show me my work orders" on the dining room screen, the frontend sends a note to the backend ("hey, get me the work orders for Alex"). The backend goes to the filing cabinet, finds the data, hands it back to the frontend, and the frontend shows it to you on screen.

All of this happens in under a second.

---

## 3. The tools — what each one is and why we needed it

### GitHub
**What it is:** A website where you store your code. Like Google Drive but for programmers.
**Why we needed it:** Multiple people (and Claude!) can see the same code, propose changes, and review each other's work before it goes live. The "main" copy is on GitHub; everyone else has copies on their own laptops.

### Git
**What it is:** The actual software that tracks every change anyone makes to the code. GitHub is the website; Git is the tool underneath.
**Why we needed it:** So we can undo mistakes, see who changed what, and combine work from different people without losing anything.

### Pull Request (PR)
**What it is:** When you've made a change to the code on your laptop, you create a "pull request" on GitHub that says "hey everyone, here are my changes, please look at them before we add them to the main code."
**Why we needed it:** It's a checkpoint. Bad changes get caught before they break the demo. We made 11 PRs during this whole deployment.

### CI (Continuous Integration)
**What it is:** A robot that lives on GitHub. Every time someone opens a PR, the robot automatically runs tests to make sure the new code doesn't break anything.
**Why we needed it:** Without it, we'd have to manually test every change. With it, the robot tells us within ~3 minutes if something's wrong.

### Docker
**What it is:** A way to package your code along with everything it needs to run (the right version of Python, all the libraries, etc.) into a single shipping container.
**Why we needed it:** "It works on my laptop" is a famous programmer joke — code that runs on your computer often doesn't run on someone else's. Docker fixes that. We pack everything into a box, and the box runs identically anywhere.

### Fly.io
**What it is:** A company that rents you space on their servers to run your Docker containers. Like renting an apartment for your software.
**Why we needed it:** Our demo has to live somewhere people can reach it on the internet. Fly.io is where it lives. They handle the boring stuff (servers, networking, certificates) so we don't have to.

### flyctl
**What it is:** A command-line tool from Fly.io. You type commands like `flyctl deploy` and it pushes your code up to Fly's servers.
**Why we needed it:** It's how we tell Fly "here's the new version, please ship it."

### PostgreSQL
**What it is:** A database. Where all the real data lives — the work orders, the users, the invoices, everything.
**Why we needed it:** Software needs to remember things. Postgres is the giant filing cabinet.

### Redis
**What it is:** Another kind of database, but for short-term, fast stuff. Like the sticky notes on the kitchen wall in our restaurant analogy.
**Why we needed it:** Some things need to be looked up incredibly fast (10,000 times per second fast). Postgres can do it, but Redis is faster for those cases. We also use it as a queue for background tasks.

### Python + FastAPI
**What it is:** Python is the programming language. FastAPI is a library that makes it easy to build the "backend" (the kitchen) in Python.
**Why we needed it:** Someone has to write the code that says "when the frontend asks for work orders, here's how to fetch them from the database." That's what FastAPI helps us do.

### TypeScript + Next.js + React
**What it is:** TypeScript is a programming language (a fancier version of JavaScript). React is a library for building user interfaces. Next.js is a framework that makes React easier to use.
**Why we needed it:** Someone has to write the code for the dining room — the buttons, the screens, the forms. That's what these are for.

### Sentry
**What it is:** A service that catches errors in your software automatically. If something crashes in the kitchen, Sentry records exactly what happened.
**Why we needed it:** Without Sentry, if something breaks for a user, you'd only know if they emailed you to complain. With Sentry, you know within 30 seconds and you see the full story of what went wrong.

### UptimeRobot
**What it is:** A service that "pings" your website every 5 minutes to make sure it's still alive. If it stops responding, UptimeRobot emails you.
**Why we needed it:** If Fly.io has a hiccup at 3am and the demo goes down, we want to know — without having to constantly check it ourselves.

---

## 4. What we actually did, step by step

### Step 0 — Get the tools ready (Phase 0)

Created a Fly.io account, installed `flyctl` on RBJ's computer, and made sure we could log into Fly from the terminal. **Result:** we had keys to the apartment.

### Step 1 — Rent the database and the sticky notes (Phase 1)

Asked Fly to set up a Postgres database (`fieldpro-poc-db`) and a Redis store (via a Fly partner called Upstash). **Result:** the filing cabinet and the sticky-note wall were ready, even though there was no kitchen yet.

### Step 2 — Get the kitchen running (Phase 2 — backend)

Took the backend code, packaged it into a Docker container, told Fly "please run this and connect it to the database," and sent it the configuration it needed (secret passwords, the database URL, etc.). The backend started running at `fieldpro-poc-backend.fly.dev`.

We hit several bumps:
- The Docker container said "run gunicorn" but gunicorn wasn't even installed (typo in the recipe)
- Fly.io needed absolute paths in the recipe (not just "run uvicorn", but "/opt/venv/bin/uvicorn")
- The database connection string was in the wrong format

Each bump was a quick fix, then redeploy.

**Result:** the kitchen was open. We could test it by asking it questions over HTTP, but no one could see it through a website yet.

### Step 3 — Open the dining room (Phase 3 — frontend)

Same as step 2 but for the frontend. The tricky part: the frontend has to know where the backend is, and that has to be baked into the frontend code at build time (not runtime). So we passed `NEXT_PUBLIC_API_URL=https://fieldpro-poc-backend.fly.dev` when building.

We hit a few more bumps:
- Next.js's type-checker found some broken links in the code that had been broken forever but never caught
- The frontend was calling the backend with the wrong URL format (trailing slashes) and the backend was redirecting in a way that broke browser security

**Result:** anyone could now visit `fieldpro-poc.fly.dev` and log in.

### Step 5 — Make it self-cleaning (Phase 5)

Wrote a script that wipes the demo data and re-creates it from scratch. Scheduled it to run automatically every day via a Fly "scheduled machine" — basically a robot that wakes up once a day, runs the script, and goes back to sleep.

**Result:** the demo resets itself every night at 3am. People can mess around all day; by morning it's pristine again.

### Step 7 — Add alarms (Phase 7, where we are now)

Two pieces:

1. **Sentry** — signed up, got a unique URL ("DSN") that identifies our project, and put it as a secret in Fly. The backend already had Sentry code in it; the moment we provided the DSN, it activated. Now every error gets recorded with full details.

   The very first thing Sentry did was tell us *exactly* why one of our endpoints had been broken for hours — a tiny SQL bug. We fixed it in 2 minutes. Without Sentry, that bug would have taken hours to find.

2. **UptimeRobot** — signed up, added two monitors: one for the backend's health endpoint, one for the frontend's login page. Both get poked every 5 minutes.

**Result:** if anything breaks, we know within minutes (or seconds, for crashes).

### Step 8 — Set up automatic deploys (Phase 8, not done yet)

Right now, when we want to update the demo, we have to manually run `flyctl deploy` from a terminal. The plan for step 8 is to wire it up so that when we merge a change into the main code on GitHub, the demo automatically redeploys with no manual work.

The setup is simple: give GitHub a "token" (kind of like a password) that lets it talk to Fly on our behalf. The deploy script already exists; it just needs that token to work.

### Step 9 — Final once-over (Phase 9, not done yet)

Run the [smoke test runbook](../runbooks/smoke-test.md) end-to-end one last time, confirm everything's solid, declare Plan A done.

---

## 5. The cool moments

A few things from this whole project that stand out:

### "Sentry paid for itself in 5 minutes"
We'd been chasing a bug for *hours* where one specific page (the dashboard) would return an error and we couldn't tell why. The error message was deliberately vague (you don't want to leak the details to attackers). We tried SSH-ing into the server, reading logs, all kinds of things — couldn't pin it down.

Then we wired up Sentry. **Five minutes later** Sentry showed us the exact line of code that was broken, the exact reason (a SQL type-inference issue), and we shipped a 2-line fix.

That's the value of monitoring. You don't realize you need it until you have it.

### The 307 redirect that strips your auth
At one point the dashboard showed empty lists for everything — no work orders, no clients, nothing. But the backend definitely had the data. After capturing the network traffic, we discovered the backend was sending "307 redirects" (which means "the URL has moved slightly, go here instead"). The browser was following the redirects, but **stripping the login token** on each redirect for security. So the redirected request hit the server unauthenticated, returned "you're not logged in", and the frontend showed empty.

The fix: change one tiny thing in the backend's URL handling. But finding it took a HAR file and some staring.

### The reset script that wipes its own backend
The first time the nightly reset ran, it dropped the database schema (correctly) but the always-on backend was still holding "cached" references to the OLD schema. So for about 10 seconds after the reset, the backend was confused and returned errors. Then SQLAlchemy (one of our libraries) auto-fixed it.

This is a "the reset works correctly, but causes a brief glitch" kind of bug. We documented it; the fix is one line for Plan B.

### Eight PRs to deploy a demo
The original plan said "one working day, simple deploy." It actually took 8 separate fix-and-redeploy cycles to land. Every cycle taught us something. None of the bugs were "OMG how could we miss that" bugs — they were the kind of bugs that only show up when you actually try to run the thing in production. Hence the full retrospective doc.

---

## 6. Where things live now

- **The demo:** https://fieldpro-poc.fly.dev (frontend) and https://fieldpro-poc-backend.fly.dev (backend)
- **The code:** https://github.com/one-repo-to-rule-them-all/poc_fieldpro
- **The database:** Fly-hosted Postgres, only reachable from inside Fly's network
- **The error tracker:** sentry.io, in RBJ's account
- **The uptime monitor:** uptimerobot.com, in RBJ's account
- **The detailed docs in this repo:**
  - [`docs/planning/roadmap.md`](../planning/roadmap.md) — what we're working on
  - [`docs/planning/plan-a.md`](../planning/plan-a.md) — the original deploy plan
  - [`docs/planning/plan-a-retrospective.md`](../planning/plan-a-retrospective.md) — what actually happened (lessons learned)
  - [`docs/planning/plan-b.md`](../planning/plan-b.md) — the next step (production onboarding)
  - [`docs/runbooks/smoke-test.md`](../runbooks/smoke-test.md) — how to verify the demo is healthy
  - [`scripts/smoke_test.py`](../../scripts/smoke_test.py) — automated version of that runbook

---

## 7. One more thing

This whole project — getting a real piece of software running on the internet, with monitoring, automated resets, login flows, role-based permissions, the whole works — is a really good example of **how much "glue" is involved in deploying software**.

The actual *coding* of FieldPro happened over weeks before this. What you saw here was 1 day of putting all the pieces together so other people can actually use it. That gap between "the code works on my laptop" and "the code works on the internet for anyone" is a huge chunk of professional software engineering.

If this kind of thing sounds interesting to you, that's basically what DevOps / Platform Engineering / SRE jobs are about. Whole careers in just the connecting-pieces-together part.
