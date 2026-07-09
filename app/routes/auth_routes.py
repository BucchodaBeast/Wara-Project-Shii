from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from ..extensions import get_supabase
from ..auth import hash_password, verify_password, issue_token

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    role = request.form.get("role", "citizen")

    if role not in ("citizen", "coordinator"):
        role = "citizen"

    if not name or not email or len(password) < 6:
        flash("Please fill in all fields (password must be 6+ characters).", "error")
        return redirect(url_for("auth.register"))

    if role == "coordinator":
        expected_code = current_app.config.get("COORDINATOR_INVITE_CODE")
        submitted_code = request.form.get("invite_code", "").strip()
        # If no code is configured, coordinator signup is disabled outright
        # rather than silently left open.
        if not expected_code or submitted_code != expected_code:
            flash("That coordinator invite code isn't valid. Sign up as a citizen, or check the code with your organizer.", "error")
            return redirect(url_for("auth.register"))

    supabase = get_supabase()
    existing = supabase.table("users").select("id").eq("email", email).execute()
    if existing.data:
        flash("An account with that email already exists.", "error")
        return redirect(url_for("auth.register"))

    user_row = {
        "name": name,
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
    }
    result = supabase.table("users").insert(user_row).execute()
    new_user = result.data[0]

    token = issue_token(new_user)
    resp = make_response(redirect(url_for("main.index")))
    resp.set_cookie("access_token", token, httponly=True, samesite="Lax", max_age=60 * 60 * 12)
    flash(f"Welcome, {new_user['name']}. Your account is ready.", "success")
    return resp


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    supabase = get_supabase()
    result = supabase.table("users").select("*").eq("email", email).execute()

    if not result.data or not verify_password(password, result.data[0]["password_hash"]):
        flash("Incorrect email or password.", "error")
        return redirect(url_for("auth.login"))

    user = result.data[0]
    token = issue_token(user)
    resp = make_response(redirect(url_for("main.index")))
    resp.set_cookie("access_token", token, httponly=True, samesite="Lax", max_age=60 * 60 * 12)
    flash(f"Welcome back, {user['name']}.", "success")
    return resp


@auth_bp.route("/logout")
def logout():
    resp = make_response(redirect(url_for("main.index")))
    resp.delete_cookie("access_token")
    flash("You've been logged out.", "success")
    return resp
