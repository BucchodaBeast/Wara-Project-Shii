from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from flask_socketio import join_room
from datetime import datetime, timezone

from ..extensions import get_supabase, socketio
from ..auth import role_required

coordinator_bp = Blueprint("coordinator", __name__)


@coordinator_bp.route("/coordinator")
@role_required("coordinator")
def dashboard():
    supabase = get_supabase()
    requests_data = supabase.table("requests").select("*").order("created_at", desc=True).execute().data
    offers_data = supabase.table("offers").select("*").order("created_at", desc=True).execute().data
    matches_data = supabase.table("matches").select("*").order("score", desc=True).execute().data

    # attach top match score to each request for the dispatch board
    matches_by_request = {}
    for m in matches_data:
        matches_by_request.setdefault(m["request_id"], []).append(m)

    for r in requests_data:
        r["top_matches"] = matches_by_request.get(r["id"], [])[:3]

    return render_template(
        "coordinator_dashboard.html",
        requests=requests_data,
        offers=offers_data,
    )


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
    join_room("coordinators")
