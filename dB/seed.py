"""
Populates Supabase with mock data for instant grading/demo.
Run with:  python db/seed.py
Requires SUPABASE_URL and SUPABASE_KEY to already be set (env or .env file).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from app.extensions import get_supabase
from app.auth import hash_password

supabase = get_supabase()

print("Seeding users...")
users = [
    {"name": "Test Citizen", "email": "citizen@test.com", "password_hash": hash_password("password123"), "role": "citizen"},
    {"name": "Test Coordinator", "email": "coordinator@test.com", "password_hash": hash_password("password123"), "role": "coordinator"},
    {"name": "Nomcebo Dlamini", "email": "nomcebo@test.com", "password_hash": hash_password("password123"), "role": "citizen"},
    {"name": "Sipho Mabuza", "email": "sipho@test.com", "password_hash": hash_password("password123"), "role": "citizen"},
    {"name": "Thandeka Nkambule", "email": "thandeka@test.com", "password_hash": hash_password("password123"), "role": "citizen"},
    {"name": "Bongani Simelane", "email": "bongani@test.com", "password_hash": hash_password("password123"), "role": "citizen"},
]
user_rows = supabase.table("users").insert(users).execute().data
citizen_ids = [u["id"] for u in user_rows if u["role"] == "citizen"]

print("Seeding requests...")
requests = [
    {"citizen_id": citizen_ids[0], "category": "water", "description": "Family of 5 needs drinking water, borehole is dry.", "urgency": "critical", "latitude": -26.3054, "longitude": 31.1367, "status": "pending", "quantity_needed": 5},
    {"citizen_id": citizen_ids[1], "category": "medical", "description": "Elderly relative needs blood pressure medication.", "urgency": "high", "latitude": -26.3200, "longitude": 31.1420, "status": "pending", "quantity_needed": 1},
    {"citizen_id": citizen_ids[2], "category": "shelter", "description": "Roof collapsed after the storm, need temporary shelter for 3.", "urgency": "critical", "latitude": -26.2990, "longitude": 31.1300, "status": "pending", "quantity_needed": 3},
    {"citizen_id": citizen_ids[3], "category": "food", "description": "Ran out of food supplies, household of 4.", "urgency": "medium", "latitude": -26.3100, "longitude": 31.1500, "status": "pending", "quantity_needed": 4},
    {"citizen_id": citizen_ids[0], "category": "food", "description": "Need baby formula urgently.", "urgency": "high", "latitude": -26.3054, "longitude": 31.1367, "status": "dispatched", "quantity_needed": 2, "quantity_fulfilled": 2},
]
request_rows = supabase.table("requests").insert(requests).execute().data
baby_formula_request = next(r for r in request_rows if "baby formula" in r["description"])

print("Seeding offers...")
offers = [
    {"citizen_id": citizen_ids[1], "resource_type": "water", "description": "20L jerrycans, 10 available.", "quantity": 10, "quantity_remaining": 10, "latitude": -26.3060, "longitude": 31.1370, "status": "available"},
    {"citizen_id": citizen_ids[2], "resource_type": "medical", "description": "First aid kit and basic medication.", "quantity": 1, "quantity_remaining": 1, "latitude": -26.3210, "longitude": 31.1430, "status": "available"},
    {"citizen_id": citizen_ids[3], "resource_type": "shelter", "description": "Spare room + 2 tents.", "quantity": 3, "quantity_remaining": 3, "latitude": -26.2995, "longitude": 31.1310, "status": "available"},
    {"citizen_id": citizen_ids[0], "resource_type": "food", "description": "Non-perishable food parcels, 6 available.", "quantity": 6, "quantity_remaining": 6, "latitude": -26.3105, "longitude": 31.1495, "status": "available"},
    {"citizen_id": citizen_ids[1], "resource_type": "transport", "description": "Pickup truck, available for deliveries.", "quantity": 1, "quantity_remaining": 1, "latitude": -26.3050, "longitude": 31.1360, "status": "available"},
    {"citizen_id": citizen_ids[2], "resource_type": "food", "description": "Baby formula, 2 tins.", "quantity": 2, "quantity_remaining": 0, "latitude": -26.3058, "longitude": 31.1365, "status": "dispatched"},
]
offer_rows = supabase.table("offers").insert(offers).execute().data
formula_offer = next(o for o in offer_rows if "Baby formula" in o["description"])

coordinator_id = next(u["id"] for u in user_rows if u["role"] == "coordinator")

print("Seeding one example dispatch (so the dispatch/contact UI has something to show)...")
supabase.table("dispatches").insert({
    "request_id": baby_formula_request["id"],
    "offer_id": formula_offer["id"],
    "coordinator_id": coordinator_id,
    "quantity": 2,
    "contact_name": "Thandeka Nkambule",
    "contact_phone": "+268 7612 3456",
    "meetup_location": "Manzini Community Hall, Main Rd",
    "meetup_notes": "Available after 5pm weekdays.",
    "status": "active",
}).execute()

print("Done. Test credentials:")
print("  Citizen:     citizen@test.com / password123")
print("  Coordinator: coordinator@test.com / password123")
