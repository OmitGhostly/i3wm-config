#!/usr/bin/env bash
# One polybar per chosen monitor; tray on the primary monitor (or the first chosen one).
# Position (top/bottom) and monitor choice come from the settings window (~/.config/i3/settings.json).
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/polybar-launch.lock"
flock 9   # one launch at a time (the settings window and i3 may both ask)
# stop the running bar(s). A bar that is still starting up can miss the first signal (two restarts in a row,
# e.g. a colour change reloads i3 while the settings window also restarts the bar), so ask again and after
# 3 seconds force it - never wait forever with no bar on screen
for _ in $(seq 1 15); do
  pgrep -u "$UID" -x polybar >/dev/null || break
  pkill -u "$UID" -x polybar 2>/dev/null
  sleep 0.2
done
pkill -KILL -u "$UID" -x polybar 2>/dev/null
while pgrep -u "$UID" -x polybar >/dev/null; do sleep 0.1; done
BAR_BOTTOM=false; BAR_MONITORS=""; BAR_HEIGHT=38; BAR_FONT=13.5; BAR_STYLE=blocks; BAR_DIVIDER=rounded
BAR_SHOW_TITLE=false; BAR_SHOW_MEDIA=false
# crisp text: grayscale anti-aliasing with light hinting (applies to programs started afterwards too)
command -v xrdb >/dev/null 2>&1 && printf 'Xft.antialias: 1\nXft.hinting: 1\nXft.hintstyle: hintslight\nXft.rgba: none\n' | xrdb -merge 2>/dev/null
eval "$(python3 "${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts/SettingsGUI.py" --bar-env 2>/dev/null)"
if [ "$BAR_BOTTOM" = true ]; then BORDER_BOTTOM=0; BORDER_TOP=1; else BORDER_BOTTOM=1; BORDER_TOP=0; fi
BAR_FONT_SPEC="FantasqueSansM Nerd Font Mono:size=${BAR_FONT:-13.5};3"
# bigger icon font (+3pt = +4px, still whole pixels) for the stay-awake mug
BAR_ICON_SPEC="FantasqueSansM Nerd Font Mono:size=$(awk -v f="${BAR_FONT:-13.5}" 'BEGIN{printf "%g", f+3}');4"
# "blocks" style: the divider at each end of a block is a Nerd Font powerline glyph, sized so it is exactly as tall
# as the bar (the glyph spans 2170/2048 of the font size; the bar's 1px border line is not part of the blocks)
case "$BAR_DIVIDER" in                            # (UTF-8 bytes, so this works whatever the locale)
  arrows)  BAR_CAP_L=$(printf '\xee\x82\xb2'); BAR_CAP_R=$(printf '\xee\x82\xb0') ;;
  slanted) BAR_CAP_L=$(printf '\xee\x82\xba'); BAR_CAP_R=$(printf '\xee\x82\xbc') ;;
  square)  BAR_CAP_L=""; BAR_CAP_R="" ;;
  *)       BAR_CAP_L=$(printf '\xee\x82\xb6'); BAR_CAP_R=$(printf '\xee\x82\xb4') ;;   # rounded (default)
esac
cap_px=$(( ( (BAR_HEIGHT - 1) * 2048 + 2169 ) / 2170 + 1 ))
# polybar places the glyph a little high; shifting it down by ~20% of its size centres it (measured at 30/38/44 px)
cap_off=$(( (cap_px * 2 + 5) / 10 ))
BAR_CAP_SPEC="FantasqueSansM Nerd Font Mono:pixelsize=${cap_px};${BAR_CAP_OFFSET:-$cap_off}"
BAR_BLOCK_GAP=1
BAR_NAME=main; [ "$BAR_STYLE" = blocks ] && BAR_NAME=blocks
# which items show: the active window's title (left) and what is playing (right) are off unless switched on
right="network bluetooth pulseaudio backlight caffeine nightlight battery cpu memory gpu date powermenu"
[ "$BAR_SHOW_MEDIA" = true ] && right="playerctl $right"
BAR_LEFT="i3"; [ "$BAR_SHOW_TITLE" = true ] && BAR_LEFT="i3 xwindow"
BAR_RIGHT="$right"
BAR_RIGHT_BLOCKS=$(for m in $right; do printf 'b-%s ' "$m"; done)
export BAR_BOTTOM BAR_HEIGHT BAR_FONT BAR_FONT_SPEC BAR_ICON_SPEC BORDER_BOTTOM BORDER_TOP BAR_STYLE \
       BAR_CAP_L BAR_CAP_R BAR_CAP_SPEC BAR_BLOCK_GAP BAR_LEFT BAR_RIGHT BAR_RIGHT_BLOCKS
all=$(polybar --list-monitors | cut -d: -f1)
sel=""
if [ -n "$BAR_MONITORS" ]; then
  for m in $all; do case " $BAR_MONITORS " in *" $m "*) sel="$sel $m" ;; esac; done
fi
[ -n "$sel" ] || sel=$all   # "all monitors", or none of the chosen ones is connected
primary=$(xrandr --query | awk '/ primary/{print $1; exit}')
sel=$(echo "$sel" | xargs)
read -r first _ <<<"$sel"
traymon=$first
[ -n "$primary" ] && case " $sel " in *" $primary "*) traymon=$primary ;; esac
for m in $sel; do
  if [ "$m" = "$traymon" ]; then tray=right; else tray=none; fi
  MONITOR=$m TRAY_POSITION=$tray polybar --reload "$BAR_NAME" >"${XDG_RUNTIME_DIR:-$HOME/.cache}/polybar-$m.log" 2>&1 9>&- &
done
