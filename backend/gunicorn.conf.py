"""
Gunicorn configuration for production deployment.
"""

import os

# Bind to PORT from environment (Railway sets this)
bind = f"0.0.0.0:{os.getenv('PORT', '5001')}"

# 2 workers — conservative since Gemini rate limits are shared across workers
workers = 2

# 120s timeout — Gemini calls with large context can be slow
timeout = 120

# Share service initialization (embedding model, caches) across workers
preload_app = True

# Log to stdout/stderr for Railway compatibility
accesslog = "-"
errorlog = "-"
loglevel = "info"
