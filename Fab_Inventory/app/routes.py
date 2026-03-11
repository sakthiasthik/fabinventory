from flask import Blueprint, render_template

main = Blueprint(
    "main",
    __name__,
    template_folder="templates",
    static_folder="static"
)

@main.route("/")
def dashboard():
    return render_template("dashboard.html")

@main.route("/projects")
def projects():
    return render_template("projects.html")

@main.route("/inventory")
def inventory():
    return render_template("inventory.html")