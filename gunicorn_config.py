import os

# Get port from environment variable or default to 10000
port = int(os.environ.get("PORT", 10000))

bind = f"0.0.0.0:{port}"
workers = 4
threads = 4
timeout = 120
# Access logfile
accesslog = "-"
# Error logfile
errorlog = "-"
# Log level
loglevel = "info"