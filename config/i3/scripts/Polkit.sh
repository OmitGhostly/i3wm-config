#!/usr/bin/env bash
pgrep -u "$UID" -f 'polkit-gnome-authentication-agent-1|polkit-kde-authentication-agent-1|lxpolkit|mate-polkit|xfce-polkit' >/dev/null && exit 0
for p in /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1 /usr/libexec/polkit-gnome-authentication-agent-1 \
  /usr/lib/x86_64-linux-gnu/polkit-gnome-authentication-agent-1 /usr/libexec/polkit-mate-authentication-agent-1 \
  /usr/lib/mate-polkit/polkit-mate-authentication-agent-1 /usr/bin/lxpolkit /usr/lib/xfce-polkit/xfce-polkit \
  /usr/lib/polkit-kde-authentication-agent-1 /usr/libexec/polkit-kde-authentication-agent-1; do
  [ -x "$p" ] && { "$p" & exit 0; }
done
notify-send "Polkit" "No polkit agent found (install polkit-gnome)"
