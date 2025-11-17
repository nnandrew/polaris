#!/bin/sh
set -e

if [ ! -f /etc/nginx/.htpasswd ]; then
  echo "Generating htpasswd file..."
  htpasswd -bc /etc/nginx/.htpasswd "$LIGHTHOUSE_ADMIN_USER" "$LIGHTHOUSE_ADMIN_PASSWORD"
else
  echo ".htpasswd already exists, skipping generation."
fi