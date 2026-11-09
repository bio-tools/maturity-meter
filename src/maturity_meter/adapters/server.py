"""Compose the generated HTTP interfaces into one deployable application.

A project with one HTTP adapter exposes it at the root. When several adapters
are selected, stable path prefixes prevent their routes from colliding.
"""

from maturity_meter.adapters.api.app import app as api_app

app = api_app
