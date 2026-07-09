import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_socketio import join_room
from datetime import datetime, timezone, date

from ..extensions import get_supabase, socketio
from ..auth import role_required, decode_token
from .citizen_routes import _to_float

coordinator_bp = Blueprint("coordinator", __name__)


@coordinator_bp.route("/coordinator")
@role_required("coordinator")
def dashboard():
    supabase = get_supabase()
    requests_data = supabase.table("requests").select("*").order("created_at", desc=True).execute().data
    offers_data = supabase.table("offers").select("*").order("created_at", desc=True).execute().data
    matches_data = supabase.table("matches").select("*").order("score", desc=True).execute().data
    dispatches_data = supabase.table("dispatches").select("*").order("created_at", desc=True).execute().data

    offers_by_id = {o["id"]: o for o in offers_data}

    # attach top match score + resolved offer details to each request, so the
    # dispatch picker can show "20L jerrycans (7 left) — 2.1km away" instead
    # of just an offer id.
    matches_by_request = {}
    for m in matches_data:
        matches_by_request.setdefault(m["request_id"], []).append(m)

    dispatches_by_request, dispatches_by_offer = {}, {}
    for d in dispatches_data:
        dispatches_by_request.setdefault(d["request_id"], []).append(d)
        dispatches_by_offer.setdefault(d["offer_id"], []).append(d)

    for r in requests_data:
        candidate_matches = matches_by_request.get(r["id"], [])
        enriched = []
        for m in candidate_matches:
            offer = offers_by_id.get(m["offer_id"])
            if not offer or offer["status"] == "resolved":
                continue
            remaining = offer.get("quantity_remaining")
            if remaining is not None and remaining <= 0:
                continue
            enriched.append({**m, "offer": offer})
        r["top_matches"] = enriched[:3]
        r["dispatches"] = dispatches_by_request.get(r["id"], [])
        r["unmatched"] = len(enriched) == 0

    for o in offers_data:
        o["dispatches"] = dispatches_by_offer.get(o["id"], [])

    # Map markers: only show entities still actionable (pending needs,
    # offers with something left to give).
    markers = []
    for r in requests_data:
        if r["status"] != "pending" or r.get("latitude") is None or r.get("longitude") is None:
            continue
        markers.append({
            "kind": "request", "id": r["id"], "lat": r["latitude"], "lng": r["longitude"],
            "label": f"{r['category'].capitalize()} — {r['urgency']}", "urgency": r["urgency"],
        })
    for o in offers_data:
        remaining = o.get("quantity_remaining")
        if o["status"] == "resolved" or (remaining is not None and remaining <= 0):
            continue
        if o.get("latitude") is None or o.get("longitude") is None:
            continue
        markers.append({
            "kind": "offer", "id": o["id"], "lat": o["latitude"], "lng": o["longitude"],
            "label": f"{o['resource_type'].capitalize()}"
                     + (f" ({remaining} left)" if remaining is not None else ""),
        })

    today = date.today().isoformat()
    stats = {
        "pending": sum(1 for r in requests_data if r["status"] == "pending"),
        "critical": sum(1 for r in requests_data if r["urgency"] == "critical" and r["status"] == "pending"),
        "available_offers": sum(1 for o in offers_data if o["status"] == "available"),
        "active_dispatches": sum(1 for d in dispatches_data if d["status"] == "active"),
        "resolved_today": sum(
            1 for r in requests_data
            if r["status"] == "resolved" and str(r.get("created_at", "")).startswith(today)
        ),
        "unmatched": sum(1 for r in requests_data if r["status"] == "pending" and r["unmatched"]),
    }

    return render_template(
        "coordinator_dashboard.html",
        requests=requests_data,
        offers=offers_data,
        stats=stats,
        map_markers_json=json.dumps(markers),
    )


@coordinator_bp.route("/coordinator/dispatch", methods=["POST"])
@role_required("coordinator")
def dispatch():
    """Links a request to an offer: allocates quantity, records contact/meetup
    details for both parties, and updates both statuses in one action instead
    of two disconnected status-column edits."""
    request_id = request.form.get("request_id", type=int)
    offer_id = request.form.get("offer_id", type=int)
    quantity = _to_float(request.form.get("quantity")) or 1.0
    contact_name = request.form.get("contact_name", "").strip()
    contact_phone = request.form.get("contact_phone", "").strip()
    meetup_location = request.form.get("meetup_location", "").strip()
    meetup_notes = request.form.get("meetup_notes", "").strip()

    supabase = get_supabase()
    req_rows = supabase.table("requests").select("*").eq("id", request_id).execute().data
    offer_rows = supabase.table("offers").select("*").eq("id", offer_id).execute().data
    if not req_rows or not offer_rows:
        flash("That request or offer no longer exists.", "error")
        return redirect(url_for("coordinator.dashboard"))
    req_row, offer_row = req_rows[0], offer_rows[0]

    still_needed = (req_row.get("quantity_needed") or 1) - (req_row.get("quantity_fulfilled") or 0)
    offer_remaining = offer_row.get("quantity_remaining")
    offer_remaining = offer_row.get("quantity") if offer_remaining is None else offer_remaining
    offer_remaining = offer_remaining if offer_remaining is not None else 1.0

    allocate = max(0.0, min(quantity, still_needed if still_needed > 0 else quantity, offer_remaining))
    if allocate <= 0:
        flash("Nothing left to allocate for that pairing — check quantities.", "error")
        return redirect(url_for("coordinator.dashboard"))

    dispatch_row = supabase.table("dispatches").insert({
        "request_id": request_id,
        "offer_id": offer_id,
        "coordinator_id": g.user["sub"],
        "quantity": allocate,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "meetup_location": meetup_location,
        "meetup_notes": meetup_notes,
        "status": "active",
    }).execute().data[0]

    new_fulfilled = (req_row.get("quantity_fulfilled") or 0) + allocate
    new_offer_remaining = offer_remaining - allocate
    new_req_status = "dispatched" if new_fulfilled >= (req_row.get("quantity_needed") or 1) else "pending"
    new_offer_status = "dispatched" if new_offer_remaining <= 0 else "available"

    supabase.table("requests").update({
        "quantity_fulfilled": new_fulfilled, "status": new_req_status,
    }).eq("id", request_id).execute()
    supabase.table("offers").update({
        "quantity_remaining": new_offer_remaining, "status": new_offer_status,
    }).eq("id", offer_id).execute()

    for entity_type, entity_id, old_status, new_status in (
        ("request", request_id, req_row["status"], new_req_status),
        ("offer", offer_id, offer_row["status"], new_offer_status),
    ):
        supabase.table("status_audit_log").insert({
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_status": old_status,
            "new_status": new_status,
            "changed_by": g.user["sub"],
            "note": f"Dispatched via pairing #{dispatch_row['id']} ({allocate:g} allocated).",
            "changed_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

    socketio.emit("dispatch_created", {
        "dispatch_id": dispatch_row["id"], "request_id": request_id, "offer_id": offer_id,
        "quantity": allocate,
    }, to="coordinators")

    flash("Dispatched — contact and meetup details are now visible to both parties.", "success")
    return redirect(url_for("coordinator.dashboard"))


@coordinator_bp.route("/coordinator/status/<entity_type>/<int:entity_id>", methods=["POST"])
@role_required("coordinator")
def update_status(entity_type, entity_id):
    if entity_type not in ("request", "offer"):
        flash("Invalid entity type.", "error")
        return redirect(url_for("coordinator.dashboard"))

    new_status = request.form.get("status")
    note = request.form.get("note", "").strip()
    table = "requests" if entity_type == "request" else "offers"

    supabase = get_supabase()
    current = supabase.table(table).select("status").eq("id", entity_id).execute().data
    old_status = current[0]["status"] if current else None

    supabase.table(table).update({"status": new_status}).eq("id", entity_id).execute()

    supabase.table("status_audit_log").insert({
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_status": old_status,
        "new_status": new_status,
        "changed_by": g.user["sub"],
        "note": note,
        "changed_at": datetime.now(timezone.utc).isoformat(),
    }).execute()

    socketio.emit("status_update", {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_status": old_status,
        "new_status": new_status,
    }, to="coordinators")

    flash("Status updated.", "success")
    return redirect(url_for("coordinator.dashboard"))


@coordinator_bp.route("/coordinator/audit/<entity_type>/<int:entity_id>")
@role_required("coordinator")
def audit_trail(entity_type, entity_id):
    supabase = get_supabase()
    logs = (
        supabase.table("status_audit_log").select("*")
        .eq("entity_type", entity_type).eq("entity_id", entity_id)
        .order("changed_at", desc=True).execute().data
    )
    return render_template("_audit_trail_partial.html", logs=logs)


@socketio.on("join_coordinator_room")
def handle_join_coordinator_room():
    # The room join is fired from client JS, so it isn't covered by
    # @role_required — verify the session cookie here too, otherwise any
    # connected socket client could listen in on the coordinator feed.
    token = request.cookies.get("access_token")
    user = decode_token(token) if token else None
    if user and user.get("role") == "coordinator":
        join_room("coordinators")
