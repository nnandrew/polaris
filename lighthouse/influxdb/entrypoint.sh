#!/bin/sh

# Create admin token file if it doesn't exist
if [ ! -f /var/lib/influxdb3/tokens/admin-token.json ]; then
    mkdir -p /var/lib/influxdb3/tokens
    cat > /var/lib/influxdb3/tokens/admin-token.json <<EOF
{
  "token": "$INFLUX_TOKEN",
  "name": "main-token",
  "expiry_millis": 1756400061529
}
EOF
fi

# Start InfluxDB
exec influxdb3 serve \
    --node-id=node0 \
    --object-store=file \
    --data-dir=/var/lib/influxdb3/data \
    --plugin-dir=/var/lib/influxdb3/plugins \
    --admin-token-file=/var/lib/influxdb3/tokens/admin-token.json