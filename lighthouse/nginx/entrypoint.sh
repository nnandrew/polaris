#!/bin/sh
set -e

# Install htpasswd if missing
if ! command -v htpasswd >/dev/null 2>&1; then
    echo "htpasswd not found — installing apache2-utils..."
    apk add --no-cache apache2-utils
fi

# Generate htpasswd file if it doesn't exist
if [ ! -f /etc/nginx/.htpasswd ]; then
  echo "Generating htpasswd file..."
  htpasswd -bc /etc/nginx/.htpasswd "$LIGHTHOUSE_ADMIN_USER" "$LIGHTHOUSE_ADMIN_PASSWORD"
else
  echo ".htpasswd already exists, skipping generation."
fi