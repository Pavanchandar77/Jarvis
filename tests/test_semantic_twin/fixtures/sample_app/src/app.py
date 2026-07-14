"""Sample generated application for Semantic Twin pipeline tests."""

from flask import Flask

app = Flask(__name__)

# Simple in-memory state
counter_state = 0


def create_app():
    """Bootstrap the sample application."""
    register_routes(app)
    return app


def register_routes(application):
    """Wire HTTP routes onto the app."""
    application.add_url_rule("/health", "health", health)
    application.add_url_rule("/items", "list_items", list_items, methods=["GET"])


@app.route("/health")
def health():
    """Liveness probe."""
    return {"ok": True}


@app.route("/items", methods=["GET"])
def list_items():
    """Return catalog items."""
    return {"items": fetch_items()}


async def fetch_items():
    """Load items from the data layer."""
    return get_catalog()


def get_catalog():
    """Catalog data access."""
    return [{"id": 1, "name": "widget"}]
