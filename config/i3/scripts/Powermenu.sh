#!/usr/bin/env bash
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/i3/rofi/config.rasi"
s="${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts"
choice=$(printf '  Lock\n  Logout\n  Suspend\n  Hibernate\n  Reboot\n  Shutdown' | rofi -dmenu -i -p "Power" -config "$cfg" -theme-str 'window {width: 18em;} listview {lines: 6;}')
confirm() { [ "$(printf 'No\nYes' | rofi -dmenu -i -p "$1?" -config "$cfg" -theme-str 'window {width: 14em;} listview {lines: 2;}')" = "Yes" ]; }
case "$choice" in
  *Lock)      "$s/LockScreen.sh" ;;
  *Logout)    confirm Logout    && i3-msg exit ;;
  *Suspend)   systemctl suspend ;;
  *Hibernate) confirm Hibernate && systemctl hibernate ;;
  *Reboot)    confirm Reboot    && systemctl reboot ;;
  *Shutdown)  confirm Shutdown  && systemctl poweroff ;;
esac
