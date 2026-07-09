from flask import Blueprint, request, jsonify, g
from ..extensions import get_supabase, socketio
from ..auth import decode_token
from .citizen_routes import _recompute_and_broadcast_matches, _to_float, _to_int

api_bp = Blueprint("api", __name__)


def _authenticated_user():
    token = request.cookies.get("access_token") or request.headers.get("Authorization", "").replace("Bearer ", "")
    return decode_token(token) if token else None


@api_bp.route("/requests", methods=["POST"])
def api_create_request():
    """
    Used by the service worker's background sync to push a need that was
    queued in IndexedDB while the citizen was offline.
    """
    user = _authenticated_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    supabase = get_supabase()
    row = {
        "citizen_id": user["sub"],
        "category": data.get("category"),
        "description": data.get("description", "").strip(),
        "urgency": data.get("urgency", "medium"),
        "latitude": _to_float(data.get("latitude")),
        "longitude": _to_float(data.get("longitude")),
        "status": "pending",
        "synced_offline": True,
        "quantity_needed": _to_float(data.get("quantity_needed")) or 1,
    }
    result = supabase.table("requests").insert(row).execute()
    new_request = result.data[0]
    _recompute_and_broadcast_matches(new_request)
    socketio.emit("new_request", new_request, to="coordinators")
    return jsonify({"ok": True, "id": new_request["id"]}), 201


@api_bp.route("/offers", methods=["POST"])
def api_create_offer():
    user = _authenticated_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401

    data = request.get_json(force=True, silent=True) or {}
    supabase = get_supabase()
    quantity = _to_int(data.get("quantity"))
    row = {
        "citizen_id": user["sub"],
        "resource_type": data.get("resource_type"),
        "description": data.get("description", "").strip(),
        "quantity": quantity,
        "quantity_remaining": quantity if quantity is not None else 1,
        "latitude": _to_float(data.get("latitude")),
        "longitude": _to_float(data.get("longitude")),
        "status": "available",
        "synced_offline": True,
    }
    result = supabase.table("offers").insert(row).execute()
    new_offer = result.data[0]
    socketio.emit("new_offer", new_offer, to="coordinators")
    return jsonify({"ok": True, "id": new_offer["id"]}), 201


@api_bp.route("/ping")
def ping():
    """Tiny endpoint the frontend polls to detect real connectivity to our
    own server (navigator.onLine alone is unreliable)."""
    return jsonify({"ok": True})
