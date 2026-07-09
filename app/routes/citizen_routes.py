from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..extensions import get_supabase, socketio
from ..auth import login_required
from ..matching_engine import compute_matches

citizen_bp = Blueprint("citizen", __name__)


@citizen_bp.route("/dashboard")
@login_required
def dashboard():
    supabase = get_supabase()
    my_requests = (
        supabase.table("requests").select("*").eq("citizen_id", g.user["sub"])
        .order("created_at", desc=True).execute().data
    )
    my_offers = (
        supabase.table("offers").select("*").eq("citizen_id", g.user["sub"])
        .order("created_at", desc=True).execute().data
    )
    return render_template("citizen_dashboard.html", requests=my_requests, offers=my_offers)


@citizen_bp.route("/report-need", methods=["GET", "POST"])
@login_required
def report_need():
    if request.method == "GET":
        return render_template("report_need.html")

    supabase = get_supabase()
    row = {
        "citizen_id": g.user["sub"],
        "category": request.form.get("category"),
        "description": request.form.get("description", "").strip(),
        "urgency": request.form.get("urgency", "medium"),
        "latitude": _to_float(request.form.get("latitude")),
        "longitude": _to_float(request.form.get("longitude")),
        "status": "pending",
        "synced_offline": request.form.get("synced_offline") == "true",
    }
    result = supabase.table("requests").insert(row).execute()
    new_request = result.data[0]

    _recompute_and_broadcast_matches(new_request)

    socketio.emit("new_request", new_request, to="coordinators")
    flash("Your request has been submitted. Help is on the way.", "success")
    return redirect(url_for("citizen.dashboard"))


@citizen_bp.route("/offer-help", methods=["GET", "POST"])
@login_required
def offer_help():
    if request.method == "GET":
        return render_template("offer_help.html")

    supabase = get_supabase()
    row = {
        "citizen_id": g.user["sub"],
        "resource_type": request.form.get("resource_type"),
        "description": request.form.get("description", "").strip(),
        "quantity": _to_int(request.form.get("quantity")),
        "latitude": _to_float(request.form.get("latitude")),
        "longitude": _to_float(request.form.get("longitude")),
        "status": "available",
        "synced_offline": request.form.get("synced_offline") == "true",
    }
    result = supabase.table("offers").insert(row).execute()
    new_offer = result.data[0]

    socketio.emit("new_offer", new_offer, to="coordinators")
    flash("Thank you — your offer is now visible to coordinators.", "success")
    return redirect(url_for("citizen.dashboard"))


def _recompute_and_broadcast_matches(request_row: dict):
    """Scores the new request against all available offers and stores results."""
    supabase = get_supabase()
    candidate_offers = supabase.table("offers").select("*").eq("status", "available").execute().data
    matches = compute_matches(request_row, candidate_offers)

    for m in matches[:10]:  # persist top 10 candidate pairings
        supabase.table("matches").insert({
            "request_id": m["request_id"],
            "offer_id": m["offer_id"],
            "score": m["score"],
            "distance_km": m["distance_km"],
        }).execute()

    if matches:
        socketio.emit("matches_computed", {
            "request_id": request_row["id"],
            "top_matches": matches[:5],
        }, to="coordinators")


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _to_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
