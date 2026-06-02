#!/bin/sh
# Copy default config if it doesn't exist in the persistent /config mount
if [ ! -f /config/config.json ]; then
    echo "Initializing default config.json in /config..."
    cp /app/config.json /config/config.json
fi

# Change working directory to the persistent /config PVC
cd /config

# Start the dashboard in the background
python /app/dashboard.py &

# Start the timelapse capture loop in the foreground
exec python /app/timelapse.py
