#!/bin/bash
set -e

# Aggressive cleanup of old locks and PIDs (important since sockets are in named volumes)
rm -rf /tmp/.X11-unix/* /tmp/.X99-lock /run/pulse/* /tmp/pulse-* 2>/dev/null || true

# Start the system D-Bus daemon before PulseAudio so its modules don't spam
# "Failed to connect to socket /run/dbus/system_bus_socket" on startup. The
# socket is non-essential for audio I/O but every module probes it.
mkdir -p /run/dbus
rm -f /run/dbus/pid 2>/dev/null || true
if command -v dbus-daemon >/dev/null 2>&1; then
  dbus-daemon --system --fork 2>/dev/null || echo "warn: dbus-daemon failed to start (continuing)"
fi

# Pre-create the pulse cookie dir so the "Failed to open cookie file" warnings
# stop. We don't need real auth — module-native-protocol-unix uses auth-anonymous=1.
mkdir -p /root/.config/pulse
touch /root/.config/pulse/cookie

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
