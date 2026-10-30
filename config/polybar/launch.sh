#!/usr/bin/env bash
# One polybar per chosen monitor; the system tray (a module, first in the right-hand list) on the primary monitor
# (or the first chosen one).
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
# defaults (the Large size, one-colour blocks), used as they are if the settings window cannot be asked
# (python missing, a damaged settings file)
F="FantasqueSansM Nerd Font Mono"
BAR_BOTTOM=false; BAR_MONITORS=""; BAR_HEIGHT=38; BAR_STYLE=solid; BAR_NAME=blocks
BAR_FONT_SPEC="$F:size=13.5;3"; BAR_ICON_SPEC="$F:size=16.5;4"; BAR_CAP_SPEC="$F:size=27.277;5"
BAR_LEFT="i3"; BAR_BATTERY=BAT0; BAR_ADAPTER=AC
BAR_RIGHT="network bluetooth pulseaudio backlight caffeine nightlight battery cpu memory gpu date powermenu"
BAR_RIGHT_B=""
# crisp text: grayscale anti-aliasing with light hinting (applies to programs started afterwards too)
command -v xrdb >/dev/null 2>&1 && printf 'Xft.antialias: 1\nXft.hinting: 1\nXft.hintstyle: hintslight\nXft.rgba: none\n' | xrdb -merge 2>/dev/null
# the saved choices (Settings > Appearance > Bar): position, size (the font lines, in exact whole pixels so the text
# is sharp), style, which items to show (an item the computer has no hardware for is left out). This also writes
# style.ini: the colours, block ends and spacing of the chosen style
eval "$(python3 "${XDG_CONFIG_HOME:-$HOME/.config}/i3/scripts/SettingsGUI.py" --bar-env 2>/dev/null)"
if [ "$BAR_BOTTOM" = true ]; then BORDER_BOTTOM=0; BORDER_TOP=1; else BORDER_BOTTOM=1; BORDER_TOP=0; fi
case "$BAR_HEIGHT" in ''|*[!0-9]*) BAR_HEIGHT=38 ;; esac
case "$BAR_NAME" in main|blocks) ;; *) BAR_NAME=blocks ;; esac
[ -n "$BAR_RIGHT_B" ] || BAR_RIGHT_B=$(for m in $BAR_RIGHT; do printf 'b-%s ' "$m"; done)
export BAR_BOTTOM BAR_HEIGHT BAR_FONT_SPEC BAR_ICON_SPEC BAR_CAP_SPEC BORDER_BOTTOM BORDER_TOP BAR_STYLE \
       BAR_LEFT BAR_RIGHT BAR_RIGHT_B BAR_BATTERY BAR_ADAPTER
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
  if [ "$m" = "$traymon" ]; then right="tray $BAR_RIGHT"; right_b="tray $BAR_RIGHT_B"; else right=$BAR_RIGHT; right_b=$BAR_RIGHT_B; fi
  MONITOR=$m BAR_RIGHT="$right" BAR_RIGHT_B="$right_b" polybar --reload "$BAR_NAME" >"${XDG_RUNTIME_DIR:-$HOME/.cache}/polybar-$m.log" 2>&1 9>&- &
done
