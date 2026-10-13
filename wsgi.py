"""WSGI entry point for Alwaysdata."""
from app import create_app

application = create_app()
