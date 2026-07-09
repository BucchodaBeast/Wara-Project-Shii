from flask import Blueprint, render_template, g, redirect, url_for, send_from_directory, current_app

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if getattr(g, "user", None):
        if g.user["role"] == "coordinator":
            return redirect(url_for("coordinator.dashboard"))
        return redirect(url_for("citizen.dashboard"))
    return render_template("landing.html")


@main_bp.route("/sw.js")
def service_worker():
    # Served at root (not /static/sw.js) so its scope covers the whole app.
    response = send_from_directory(f"{current_app.static_folder}/js", "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Content-Type"] = "application/javascript"
    return response
