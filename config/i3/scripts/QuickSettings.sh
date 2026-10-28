#!/usr/bin/env bash
cfgd="${XDG_CONFIG_HOME:-$HOME/.config}"
source "$cfgd/i3/defaults.conf" 2>/dev/null
edit() { ${term:-kitty} -e ${editor:-nano} "$1"; }
pkill rofi 2>/dev/null
c=$(printf '%s\n' "Edit i3 config" "Edit defaults (apps)" "Edit polybar" "Edit picom" "Edit rofi config" "Edit dunst" "Change wallpaper" "Reload i3" "Restart i3" "Refresh bar/colors" |
    rofi -dmenu -i -p "Quick settings" -config "$cfgd/i3/rofi/config.rasi")
case "$c" in
  "Edit i3 config") edit "$cfgd/i3/config" ;;
  "Edit defaults (apps)") edit "$cfgd/i3/defaults.conf" ;;
  "Edit polybar") edit "$cfgd/polybar/config.ini" ;;
  "Edit picom") edit "$cfgd/picom/picom.conf" ;;
  "Edit rofi config") edit "$cfgd/i3/rofi/config.rasi" ;;
  "Edit dunst") edit "$cfgd/dunst/dunstrc" ;;
  "Change wallpaper") "$cfgd/i3/scripts/Wallpaper.sh" --select ;;
  "Reload i3") i3-msg reload ;;
  "Restart i3") i3-msg restart ;;
  "Refresh bar/colors") "$cfgd/i3/scripts/Refresh.sh" ;;
esac
