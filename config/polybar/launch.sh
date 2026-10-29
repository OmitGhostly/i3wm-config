#!/usr/bin/env bash
# One polybar per chosen monitor; tray on the primary monitor (or the first chosen one).
# Position (top/bottom) and monitor choice come from the settings window (~/.config/i3/settings.json).
exec 9>"${XDG_RUNTIME_DIR:-/tmp}/polybar-launch.lock"
flock 9   # one launch at a time (the settings window and i3 may both ask)
pkill -u "$UID" -x polybar 2>/dev/null
while pgrep -u "$UID" -x polybar >/dev/null; do sleep 0.2; done
BAR_BOTTOM=false; BAR_MONITORS=""; BAR_HEIGHT=38; BAR_FONT=13.5
# crisp text: grayscale anti-aliasing with light hinting (applies to programs started afterwards too)
command -v xrdb >/dev/null 2>&1 && printf 'Xft.antialias: 1\nXft.hinting: 1\nXft.hintstyle: hintslight\nXft.rgba: none\n' | xrdb -merge 2>/dev/null
eval "$(python3 "${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts/SettingsGUI.py" --bar-env 2>/dev/null)"
if [ "$BAR_BOTTOM" = true ]; then BORDER_BOTTOM=0; BORDER_TOP=1; else BORDER_BOTTOM=1; BORDER_TOP=0; fi
BAR_FONT_SPEC="FantasqueSansM Nerd Font Mono:size=${BAR_FONT:-13.5};3"
# bigger icon font (+3pt = +4px, still whole pixels) for the stay-awake mug
BAR_ICON_SPEC="FantasqueSansM Nerd Font Mono:size=$(awk -v f="${BAR_FONT:-13.5}" 'BEGIN{printf "%g", f+3}');4"
export BAR_BOTTOM BAR_HEIGHT BAR_FONT BAR_FONT_SPEC BAR_ICON_SPEC BORDER_BOTTOM BORDER_TOP
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
  MONITOR=$m TRAY_POSITION=$tray polybar --reload main >"${XDG_RUNTIME_DIR:-$HOME/.cache}/polybar-$m.log" 2>&1 9>&- &
done
