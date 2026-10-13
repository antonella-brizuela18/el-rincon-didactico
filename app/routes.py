"""Public routes for the initial store scaffold."""
from flask import Blueprint, jsonify, render_template

main = Blueprint("main", __name__)


@main.get("/")
def home():
    return render_template("index.html")


@main.get("/health")
def health():
    # Does not expose credentials or database details.
    return jsonify(status="ok", service="el-rincon-didactico"), 200
