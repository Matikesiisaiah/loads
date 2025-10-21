
# LoadBoard Flask (Render-ready)

A minimal load board web application inspired by Doft's load board. Shippers can post loads, carriers can list trucks, both can match by equipment and distance, chat inside a booking, and update booking status.

## Features
- User auth (shipper, carrier, admin)
- Post/search loads
- List/search trucks
- One-click matching by equipment + radius (Haversine)
- Bookings workflow (pending → accepted → in_transit → delivered / cancelled)
- Per-booking chat messages
- Favorites (save loads)
- Admin demo-data seeding
- JSON APIs: `/api/loads`, `/api/trucks`

## Quickstart (Local)
```bash
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export FLASK_APP=wsgi:app  # Windows: set FLASK_APP=wsgi:app
export SECRET_KEY=dev-secret  # set your own secret in production
flask run
```
Then open http://127.0.0.1:5000

Create an admin user by registering normally, then update your role in the DB or use SQLite tool. Alternatively, after registering, temporarily flip role to "admin" through an SQLite editor.

## Deploy to Render
- Push this repo to GitHub
- Create a **Web Service** on Render
- Root directory: repository root
- Render auto-detects `render.yaml`
- Start command: defined as `gunicorn wsgi:app`
- Add an environment variable `SECRET_KEY` (auto-generated in `render.yaml` too)

## Notes
- Geocoding is manual (you enter lat/lon). This keeps the demo dependency-free.
- For payments, rate cards, bidding, or doc uploads, add blueprints as needed.
- DB: SQLite by default; on Render, set `DATABASE_URL` to a managed Postgres URL and SQLAlchemy will use it.
