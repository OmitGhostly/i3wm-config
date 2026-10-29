#!/usr/bin/env bash
# Monochrome fastfetch with a shiny Mimikyu sprite from acxz/pokescript (https://github.com/acxz/pokescript).
# The sprite is read from the pokescript clone the installer makes; a copy ships with the config as a fallback.
cfgdir="${XDG_CONFIG_HOME:-$HOME/.config}"
cfg="$cfgdir/fastfetch/config-pokemon.jsonc"
command -v fastfetch >/dev/null || exit 0
# Greet only once per terminal window, no matter how many times this is called (a duplicated line in .zshrc,
# a shell that restarts itself, a prompt theme that re-reads the rc file...). The key is the terminal's session.
sid=$(ps -o sid= -p $$ 2>/dev/null | tr -d ' ')
if [ -n "$sid" ]; then
  started=$(ps -o lstart= -p "$sid" 2>/dev/null | tr -c 'A-Za-z0-9' '_')
  lockdir="${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/i3dots-pokefetch-$UID"
  mkdir -p "$lockdir" 2>/dev/null && chmod 700 "$lockdir" 2>/dev/null
  find "$lockdir" -type f -mtime +1 -delete 2>/dev/null
  mark="$lockdir/$sid-$started"
  [ -e "$mark" ] && exit 0
  : > "$mark"
fi
for sprite in \
    "${POKESCRIPT_DIR:-${XDG_DATA_HOME:-$HOME/.local/share}/pokescript}/colorscripts/shiny/mimikyu.txt" \
    /usr/local/opt/pokemon-colorscripts/colorscripts/shiny/mimikyu.txt \
    /usr/share/pokemon-colorscripts/colorscripts/shiny/mimikyu.txt \
    "$cfgdir/fastfetch/shiny-mimikyu.txt"; do
  if [ -r "$sprite" ]; then
    # file-raw logos need their size: rows = lines, columns = widest line without colour codes (block = 1 column)
    h=$(wc -l < "$sprite")
    w=$(sed 's/\x1b\[[0-9;]*m//g; s/█/X/g' "$sprite" | awk '{ if (length($0) > m) m = length($0) } END { print m + 0 }')
    exec fastfetch -c "$cfg" --logo-type file-raw --logo "$sprite" --logo-width "$w" --logo-height "$h" --logo-padding-right 3 2>/dev/null
  fi
done
exec fastfetch -c "$cfg"
