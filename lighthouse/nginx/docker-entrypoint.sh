#!/bin/sh
envsubst '$LIGHTHOUSE_HOSTNAME' < /etc/nginx/conf.d/app.conf > /etc/nginx/conf.d/default.conf
exec nginx -g 'daemon off;'