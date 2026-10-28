#!/usr/bin/env bash
# What Hyprland's [input] block did. Edit layout here (e.g. "us,de").
setxkbmap -layout us -option grp:alt_shift_toggle
xset r rate 300 50
command -v numlockx >/dev/null && numlockx on
xset s 600 5; xset +dpms; xset dpms 0 0 720
if command -v xinput >/dev/null; then
  xinput list --name-only | grep -iE 'touchpad|trackpad' | while read -r dev; do
    for p in "libinput Tapping Enabled" "libinput Natural Scrolling Enabled" "libinput Disable While Typing Enabled"; do
      xinput set-prop "$dev" "$p" 1 2>/dev/null
    done
  done
fi
