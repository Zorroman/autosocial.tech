import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ADM.tools/Passenger entrypoint
from app import app as application  # noqa: F401 -- Passenger/WSGI looks up `application` by name

