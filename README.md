# Community Emergency & Resource Dispatcher

MCS 306 practical test — a lightweight platform for coordinating community aid
during localized crises (storms, floods, outages) when centralized emergency
services get overwhelmed.

## Prerequisites
- Python 3.11+
- A free Supabase project (https://supabase.com) — just need the URL and API key
- pip

## Setup

1. Clone/unzip this repo and `cd` into it.

2. Create a virtual environment and install dependencies:
   ```
   python -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up the database — open your Supabase project's SQL editor and run
   everything in `db/schema.sql`.

4. Copy `.env.example` to `.env` and fill in your Supabase project's URL and
   API key (`Project Settings → API` in the Supabase dashboard):
   ```
   cp .env.example .env
   ```

5. Seed some mock data so there's something to see immediately:
   ```
   python db/seed.py
   ```

6. Run it:
   ```
   python run.py
   ```
   App runs at http://localhost:5000

## Deploying (Render)

- Build command: `pip install -r requirements.txt`
- Start command: (already set in `Procfile`) `gunicorn --worker-class eventlet -w 1 run:app`
- Add `SUPABASE_URL`, `SUPABASE_KEY`, `JWT_SECRET`, `FLASK_SECRET_KEY` as
  environment variables in the Render dashboard — don't commit `.env`.

## Test credentials

After running the seed script:

| Role        | Email                | Password    |
|-------------|-----------------------|-------------|
| Citizen     | citizen@test.com      | password123 |
| Coordinator | coordinator@test.com  | password123 |

## Walkthrough video

[INSERT UNLISTED YOUTUBE/LOOM LINK HERE]

## Architecture & design decisions

**Three-tier:** Presentation is server-rendered Jinja templates + vanilla JS
(`app/templates`, `app/static`). Logic lives in `app/routes/*` and the
isolated `app/matching_engine.py`. Persistence is entirely in Supabase
(Postgres), accessed only through `app/extensions.py`.

**Offline-first.** The citizen forms submit through `submitWithOfflineFallback()`
in `offline-sync.js`: if the request fails (no connection), the submission is
saved to IndexedDB instead of being lost, and a service worker
(`static/js/sw.js`) triggers a background sync to flush the queue the moment
connectivity comes back. This isn't cosmetic — it's the actual point of the
brief: coordination shouldn't stop just because the network did.

**Weighted matching engine, not a filter.** `app/matching_engine.py` scores
every request/offer pairing with `0.4×urgency + 0.35×proximity(haversine) +
0.25×resource-type match`, instead of a plain dropdown filter. It's pure and
has no DB/network calls, so it's covered by `tests/test_matching_engine.py`
independently of the rest of the app.

**Audit trail.** Every status change (pending → dispatched → resolved) writes
a row to `status_audit_log` with who changed it, when, and why — visible per
request/offer on the coordinator dashboard instead of just overwriting a
status column.

**Live dashboard.** Flask-SocketIO pushes new requests, new offers, and
status changes to connected coordinators in real time — no manual refresh.

## Running the tests

```
pip install pytest
python -m pytest tests/ -v
```
