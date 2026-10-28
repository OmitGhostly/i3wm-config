#!/usr/bin/env bash
# X11 version of the grim/slurp script. Needs: maim xdotool xclip (optional: swappy/flameshot)
dir="$HOME/Pictures/Screenshots"; mkdir -p "$dir"
f="$dir/Screenshot_$(date +%d-%b_%H-%M-%S)_$RANDOM.png"
icons="${XDG_CONFIG_HOME:-$HOME/.config}/i3/icons"
finish() {
  [ -s "$f" ] || { notify-send -u low "Screenshot" "cancelled"; exit 1; }
  xclip -selection clipboard -t image/png -i "$f"
  "${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts/Sounds.sh" --screenshot 2>/dev/null
  notify-send -i "$f" "Screenshot saved" "$f (also copied to clipboard)"
}
countdown() { for ((i=$1;i>0;i--)); do notify-send -t 900 -h string:x-dunst-stack-tag:shot "Screenshot in $i"; sleep 1; done; }
case "$1" in
  --now)    maim "$f"; finish ;;
  --in5)    countdown 5;  maim "$f"; finish ;;
  --in10)   countdown 10; maim "$f"; finish ;;
  --active) maim -i "$(xdotool getactivewindow)" "$f"; finish ;;
  --area)   maim -s -u -b 2 "$f" 2>/dev/null; finish ;;
  --swappy)
    if command -v swappy >/dev/null; then maim -s -u | swappy -f -
    elif command -v flameshot >/dev/null; then flameshot gui
    else notify-send "Screenshot" "install swappy or flameshot"; fi ;;
  *) echo "usage: $0 --now|--area|--active|--in5|--in10|--swappy"; exit 1 ;;
esac
