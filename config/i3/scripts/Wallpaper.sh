#!/usr/bin/env bash
# feh replacement for swww/awww. Usage: Wallpaper.sh --select | --random | --restore | --set FILE
WALL_DIR="${WALL_DIR:-$HOME/Pictures/wallpapers}"
cache="${XDG_CACHE_HOME:-$HOME/.cache}/i3"; mkdir -p "$cache"
cfg="${XDG_CONFIG_HOME:-$HOME/.config}/i3"
set_wall() {
  local f; f=$(readlink -f "$1") || exit 1
  [ -f "$f" ] || { notify-send "Wallpaper" "not found: $f"; exit 1; }
  feh --no-fehbg --bg-fill "$f"
  ln -sf "$f" "$cache/current_wallpaper"
  "$cfg/scripts/RofiFocusedWallpaperLink.sh" >/dev/null 2>&1 || true
}
list() { find -L "$WALL_DIR" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.webp' \) | sort; }
case "$1" in
  --set)     set_wall "$2" ;;
  --restore) if [ -e "$cache/current_wallpaper" ]; then "$cfg/scripts/RofiFocusedWallpaperLink.sh" >/dev/null 2>&1; feh --no-fehbg --bg-fill "$cache/current_wallpaper"
             else f=$(list | shuf -n1); [ -n "$f" ] && set_wall "$f"; fi ;;
  --random)  f=$(list | shuf -n1); if [ -n "$f" ]; then set_wall "$f"; else notify-send "Wallpaper" "no images in $WALL_DIR"; fi ;;
  --select|"")
    pkill rofi 2>/dev/null
    sel=$(list | while read -r p; do printf '%s\0icon\x1f%s\n' "$(basename "$p")" "$p"; done |
          rofi -dmenu -i -show-icons -p "Wallpaper" -config "$cfg/rofi/config-wallpaper.rasi")
    [ -n "$sel" ] && set_wall "$(list | grep -F -m1 "/$sel")" ;;
esac
