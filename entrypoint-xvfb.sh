#!/bin/bash
set -e

# Aggressive cleanup of old locks and PIDs (important since sockets are in named volumes)
rm -rf /tmp/.X11-unix/* /tmp/.X99-lock /run/pulse/* /tmp/pulse-* 2>/dev/null || true

# Start Xvfb
Xvfb :99 -screen 0 1280x1200x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
sleep 2

# Start PulseAudio (single line to avoid parsing errors)
/usr/bin/pulseaudio --daemonize=no --log-target=stderr --exit-idle-time=-1 -n -F /dev/null --load="module-native-protocol-unix socket=/run/pulse/native auth-anonymous=1" --load="module-null-sink sink_name=zam sink_properties='device.description=zam'" &
PULSE_PID=$!

sleep 5

# Set defaults
/usr/bin/pactl set-default-sink zam 2>/dev/null || true
/usr/bin/pactl set-default-source zam.monitor 2>/dev/null || true

echo 'Xvfb and PulseAudio are ready'
wait $XVFB_PID $PULSE_PID
