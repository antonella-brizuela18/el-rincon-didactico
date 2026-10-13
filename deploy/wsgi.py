"""Select this WSGI entry point in Alwaysdata to use private JSON settings."""
import sys
from pathlib import Path

project = Path(__file__).resolve().parents[1]
if str(project) not in sys.path:
    sys.path.insert(0, str(project))

from deploy.settings import load_settings
load_settings()

from app import create_app
application = create_app()
