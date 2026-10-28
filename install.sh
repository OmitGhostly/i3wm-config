#!/usr/bin/env bash
# =============================================================================
#  i3wm-dots installer  -  installs i3 + everything it needs + the dotfiles
#  Port of LinuxBeginnings/Hyprland-Dots (GPL-3.0-or-later)
#
#  Works from KDE, GNOME, or any other desktop: it installs i3 and Xorg next to
#  your current desktop, so you can pick "i3" at the login screen.
#
#  Usage:  ./install.sh [options]
#    (default)       install i3 + dependencies, then the dotfiles
#    --no-packages   only copy the dotfiles (you already have the programs)
#    --wallpapers    also download the full KooL wallpaper bank (large)
#    --no-pokemon    skip pokescript and the shiny Mimikyu fastfetch greeting in the terminal
#    --no-ghostty    do not install Ghostty (kitty is used as the terminal instead)
#    --no-backup     overwrite existing configs instead of moving them aside
#    --restore       put back the newest *.bak-* backups and exit
#    --dry-run       show what would happen without changing anything
#    -h, --help      show this help
#
#  One-liner (no clone needed):
#    bash <(curl -fsSL https://raw.githubusercontent.com/OmitGhostly/i3wm-config/main/install.sh)
#
#  Package managers: dnf (Fedora - the main target), pacman (Arch & derivatives),
#  apt (Debian, Ubuntu, Mint, Pop!_OS). Anything else: install the programs
#  yourself, then run with --no-packages.
#  A log of every run is written to ~/.cache/i3wm-dots-install.log
# =============================================================================
set -uo pipefail

REPO_URL="${I3DOTS_REPO:-https://github.com/OmitGhostly/i3wm-config.git}"
here="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || echo /)"
cfg="${XDG_CONFIG_HOME:-$HOME/.config}"
stamp="$(date +%Y%m%d-%H%M%S)"
do_packages=1; do_wallpapers=0; do_pokemon=1; do_ghostty=1; do_backup=1; do_restore=0; dry=0
export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

say()  { printf '\033[1;35m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m %s\n' "$*" >&2; exit 1; }
usage() { sed -n '2,30p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

for arg in "$@"; do
  case "$arg" in
    --no-packages) do_packages=0 ;;
    --packages)    do_packages=1 ;;           # kept for old instructions; now the default
    --wallpapers)  do_wallpapers=1 ;;
    --no-pokemon)  do_pokemon=0 ;;
    --no-ghostty)  do_ghostty=0 ;;
    --no-backup)   do_backup=0 ;;
    --restore)     do_restore=1 ;;
    --dry-run)     dry=1 ;;
    -h|--help)     usage; exit 0 ;;
    *) die "unknown option: $arg (try --help)" ;;
  esac
done

# run a command, or just print it in --dry-run mode
run() { if [ "$dry" -eq 1 ]; then printf '   + %s\n' "$*"; return 0; fi; "$@"; }

# ---- log everything (not in dry-run) -----------------------------------------
if [ "$dry" -eq 0 ]; then
  mkdir -p "$HOME/.cache" 2>/dev/null || true
  LOG="$HOME/.cache/i3wm-dots-install.log"
  exec > >(tee -a "$LOG") 2>&1
  say "log: $LOG"
fi

# ---- privileges ---------------------------------------------------------------
if [ "$(id -u)" -eq 0 ]; then
  [ "${I3DOTS_ALLOW_ROOT:-0}" = 1 ] || die "run as your normal user, not root (sudo is asked for only when installing packages)"
  SUDO=""
else
  SUDO="sudo"
  if [ "$do_packages" -eq 1 ] && ! command -v sudo >/dev/null 2>&1; then
    die "sudo is required to install packages. Install it, or run with --no-packages"
  fi
fi

# ---- distro detection -----------------------------------------------------------
detect_family() {
  local f="${I3DOTS_OS_RELEASE:-/etc/os-release}" id="" like=""
  if [ -r "$f" ]; then
    # shellcheck source=/dev/null
    id="$( . "$f"; echo "${ID:-}" )"
    # shellcheck source=/dev/null
    like="$( . "$f"; echo "${ID_LIKE:-}" )"
  fi
  case " $id $like " in
    *" fedora "*|*" rhel "*|*" centos "*)          echo fedora ;;
    *" arch "*|*" archlinux "*)                    echo arch ;;
    *" debian "*|*" ubuntu "*)                     echo debian ;;
    *)                                             echo unknown ;;
  esac
}
FAMILY="$(detect_family)"

# ---- bootstrap: script was run without the repo next to it (curl | bash) -------
if [ ! -d "$here/config" ]; then
  say "repository files not found next to the script - fetching them"
  if ! command -v git >/dev/null 2>&1; then
    case "$FAMILY" in
      fedora) run $SUDO dnf install -y git ;;
      arch)   run $SUDO pacman -S --needed --noconfirm git ;;
      debian) run $SUDO apt-get update; run $SUDO apt-get install -y git ;;
      *) die "git is needed to download the dotfiles - install git and re-run" ;;
    esac
  fi
  dest="${XDG_DATA_HOME:-$HOME/.local/share}/i3wm-dots"
  if [ -d "$dest/.git" ]; then run git -C "$dest" pull --ff-only || warn "could not update $dest, using what is there"
  else run git clone --depth=1 "$REPO_URL" "$dest" || die "clone failed: $REPO_URL"; fi
  [ "$dry" -eq 1 ] && { say "dry-run: would continue with $dest/install.sh"; exit 0; }
  exec bash "$dest/install.sh" "$@"
fi

# ---- restore --------------------------------------------------------------------
if [ "$do_restore" -eq 1 ]; then
  for d in "$here"/config/*/; do
    name="$(basename "$d")"
    latest="$(ls -d "$cfg/$name".bak-* 2>/dev/null | sort | tail -n1 || true)"
    if [ -n "$latest" ]; then
      run rm -rf "${cfg:?}/$name"; run mv "$latest" "$cfg/$name"; say "restored $name from $(basename "$latest")"
    fi
  done
  exit 0
fi

# =============================================================================
#  Packages.  "a|b" = use a if the repo has it, otherwise b.  A leading "/" is a
#  file path (dnf resolves it to whichever package ships it - robust to renames).
#  Every entry is checked against the repos first; entries that do not exist on
#  your distro are skipped and reported at the end, so one bad name can never
#  abort the installation of everything else.
# =============================================================================
packages_for() {
  local common="polybar picom dunst rofi kitty feh maim xdotool xclip xss-lock i3lock imagemagick
    brightnessctl pamixer playerctl pavucontrol redshift numlockx jq curl unzip arandr git mpv xdg-utils
    fontconfig lxappearance fastfetch python3 bluez blueman clipmenu|copyq"
  case "$FAMILY" in
    fedora) echo "i3 xorg-x11-server-Xorg xset|/usr/bin/xset xrdb|/usr/bin/xrdb xsetroot|/usr/bin/xsetroot adwaita-cursor-theme xrandr|/usr/bin/xrandr
                  xprop|/usr/bin/xprop xdpyinfo|/usr/bin/xdpyinfo setxkbmap|/usr/bin/setxkbmap xinput|/usr/bin/xinput
                  network-manager-applet thunar polkit-gnome libnotify|/usr/bin/notify-send
                  libqalculate|/usr/bin/qalc google-noto-color-emoji-fonts|google-noto-emoji-color-fonts
                  swappy python3-gobject gtk3 $common" ;;
    arch)   echo "i3-wm xorg-server xorg-xset xorg-xrdb xorg-xsetroot adwaita-icon-theme xorg-xrandr xorg-xprop xorg-xdpyinfo xorg-setxkbmap xorg-xinput
                  network-manager-applet thunar polkit-gnome libnotify libqalculate swappy
                  noto-fonts-emoji python-gobject gtk3 $common" ;;
    debian) echo "i3 xserver-xorg x11-xserver-utils x11-utils x11-xkb-utils xinput network-manager-gnome thunar
                  policykit-1-gnome|polkit-gnome|lxpolkit libnotify-bin qalc|libqalculate-utils
                  fonts-noto-color-emoji python3-gi gir1.2-gtk-3.0 $common" ;;
  esac
}

pkg_available() {
  case "$FAMILY" in
    fedora) dnf -q repoquery --whatprovides "$1" 2>/dev/null | grep -q . ;;
    arch)   pacman -Si "$1" >/dev/null 2>&1 ;;
    debian) [ -n "$(apt-cache policy "$1" 2>/dev/null | awk '/Candidate:/{print $2}' | grep -v '^(none)$')" ] ;;
    *)      return 1 ;;
  esac
}

pkg_install() {   # pkg_install pkg...
  case "$FAMILY" in
    fedora) run $SUDO dnf install -y "$@" ;;
    arch)   run $SUDO pacman -S --needed --noconfirm "$@" ;;
    debian) run $SUDO apt-get install -y "$@" ;;
  esac
}

missing=()

# pinned to a reviewed commit: the sprite is printed straight into your terminal, so it must not change under you
POKESCRIPT_REV="efb573d81beacf629d981b4997ed304ce3c34b8c"
install_pokemon() {   # acxz/pokescript: the shiny Mimikyu sprite shown by fastfetch in the terminal
  [ "$do_pokemon" -eq 1 ] || return 0
  command -v git >/dev/null 2>&1 || return 0
  local dest="${XDG_DATA_HOME:-$HOME/.local/share}/pokescript"
  if [ "$dry" -eq 0 ] && [ "$(git -C "$dest" rev-parse HEAD 2>/dev/null)" = "$POKESCRIPT_REV" ]; then return 0; fi
  say "installing pokescript (acxz/pokescript @ ${POKESCRIPT_REV:0:7}) for the Mimikyu greeting"
  run rm -rf "$dest"
  run mkdir -p "$dest"
  if run git -C "$dest" init -q \
     && run git -C "$dest" fetch -q --depth 1 https://github.com/acxz/pokescript.git "$POKESCRIPT_REV" \
     && run git -C "$dest" checkout -q FETCH_HEAD; then :
  else
    warn "could not download pokescript - the bundled Mimikyu sprite is used instead"
    run rm -rf "$dest"
  fi
}

# add the Pokemon fastfetch line to the shell rc files (once; an older kitty-only line is upgraded)
install_shell_hook() {
  [ "$do_pokemon" -eq 1 ] || return 0
  local rc marker='# i3wm-dots: pokemon fastfetch'
  local line='{ [ -n "$KITTY_WINDOW_ID" ] || [ "$TERM_PROGRAM" = ghostty ]; } && [ -x "$HOME/.config/i3/scripts/PokeFetch.sh" ] && "$HOME/.config/i3/scripts/PokeFetch.sh"'
  for rc in "$HOME/.zshrc" "$HOME/.bashrc"; do
    [ -f "$rc" ] || continue
    if grep -qF "$marker" "$rc" 2>/dev/null; then
      grep -qF 'TERM_PROGRAM' "$rc" && continue
      say "upgrading the pokemon fastfetch greeting in $rc (kitty + ghostty)"
      [ "$dry" -eq 1 ] && continue
      awk -v m="$marker" -v l="$line" 'f{print l; f=0; next} {print} index($0,m){f=1}' "$rc" > "$rc.i3tmp" && mv "$rc.i3tmp" "$rc"
      continue
    fi
    say "adding the pokemon fastfetch greeting to $rc (kitty and ghostty only)"
    [ "$dry" -eq 1 ] || printf '\n%s\n%s\n' "$marker" "$line" >> "$rc"
  done
}

# Ghostty is the default terminal. Fedora has no official package (community COPR pgdev/ghostty),
# Arch has it in the official repos, Debian/Ubuntu have none (kitty is used there).
install_ghostty() {
  [ "$do_ghostty" -eq 1 ] || return 0
  command -v ghostty >/dev/null 2>&1 && return 0
  case "$FAMILY" in
    fedora)
      say "installing Ghostty from the community COPR pgdev/ghostty (Fedora has no official package)"
      run $SUDO dnf copr enable -y pgdev/ghostty \
        || { run $SUDO dnf install -y dnf-plugins-core && run $SUDO dnf copr enable -y pgdev/ghostty; } \
        || { warn "could not enable the Ghostty COPR - kitty will be your terminal"; return 0; }
      run $SUDO dnf install -y ghostty || warn "Ghostty install failed - kitty will be your terminal" ;;
    arch)
      say "installing Ghostty"
      pkg_install ghostty || warn "Ghostty install failed - kitty will be your terminal" ;;
    debian)
      warn "Ghostty has no official Debian/Ubuntu package - kitty will be your terminal (see ghostty.org/docs/install/binary)" ;;
  esac
}

# use ghostty as the terminal when it is installed, otherwise kitty (the configs ship with ghostty)
choose_terminal() {
  local t=ghostty
  command -v ghostty >/dev/null 2>&1 || t=kitty
  [ "$dry" -eq 1 ] && { say "terminal: ghostty if it installs, otherwise kitty"; return 0; }
  say "default terminal: $t"
  sed -i "s/^term=.*/term=\"$t\"/" "$cfg/i3/defaults.conf" 2>/dev/null || true
  sed -i "s/^\( *terminal: \).*/\1\"$t\";/" "$cfg/i3/rofi/00-terminal.rasi" 2>/dev/null || true
}

install_packages() {
  if [ "$FAMILY" = unknown ]; then
    warn "Unsupported distro (automated: Fedora, Arch and Debian/Ubuntu families)."
    warn "Install yourself:  i3 (>=4.22) xorg polybar picom dunst rofi kitty feh maim xdotool xclip xss-lock i3lock"
    warn "  imagemagick brightnessctl pamixer playerctl pavucontrol nm-applet redshift clipmenu|copyq numlockx xinput"
    warn "  xrandr xprop xdpyinfo setxkbmap libnotify mpv qalc jq curl arandr thunar polkit-gnome lxappearance fastfetch bluez blueman"
    warn "then re-run with --no-packages"
    return 0
  fi
  say "$FAMILY-based system detected - checking which packages your repos provide"
  [ "$FAMILY" = debian ] && run $SUDO apt-get update

  local have=() item pick alt alts
  # shellcheck disable=SC2046
  for item in $(packages_for); do
    pick=""
    IFS='|' read -ra alts <<<"$item"
    for alt in "${alts[@]}"; do
      if [ "$dry" -eq 1 ] || pkg_available "$alt"; then pick="$alt"; break; fi
    done
    if [ -n "$pick" ]; then have+=("$pick"); else missing+=("${item//|/ or }"); fi
  done

  say "installing ${#have[@]} packages"
  if ! pkg_install "${have[@]}"; then
    warn "bulk install failed - retrying one package at a time so a single problem cannot block the rest"
    [ "$FAMILY" = arch ] && warn "(if pacman reported 404s, run 'sudo pacman -Syu' once and re-run this script)"
    local p
    for p in "${have[@]}"; do pkg_install "$p" || missing+=("$p"); done
  fi

  # Arch: try the AUR for anything the official repos did not have
  if [ "$FAMILY" = arch ] && [ "${#missing[@]}" -gt 0 ]; then
    local helper="" h m still=()
    for h in paru yay; do command -v "$h" >/dev/null 2>&1 && { helper="$h"; break; }; done
    if [ -n "$helper" ]; then
      say "trying the AUR with $helper for: ${missing[*]}"
      for m in "${missing[@]}"; do run "$helper" -S --needed --noconfirm "$m" || still+=("$m"); done
      missing=("${still[@]}")
    fi
  fi

  install_ghostty
}

install_font() {
  command -v fc-list >/dev/null 2>&1 || return 0
  if fc-list 2>/dev/null | grep -qi 'fantasque.*nerd\|nerd.*fantasque'; then return 0; fi
  if command -v curl >/dev/null 2>&1 && command -v unzip >/dev/null 2>&1; then
    say "installing FantasqueSansM Nerd Font (icons in the bar and terminal)"
    local fd="${XDG_DATA_HOME:-$HOME/.local/share}/fonts/FantasqueSansMNerd" tmp
    tmp="$(mktemp -d)"
    if run curl -fsSL -o "$tmp/f.zip" "https://github.com/ryanoasis/nerd-fonts/releases/latest/download/FantasqueSansMono.zip" \
       && run mkdir -p "$fd" && run unzip -qo "$tmp/f.zip" -d "$fd"; then
      run fc-cache -f "$fd" >/dev/null 2>&1
    else
      warn "font download failed - install 'FantasqueSansM Nerd Font' yourself (nerdfonts.com) or icons will look broken"
    fi
    rm -rf "$tmp"
  else
    warn "FantasqueSansM Nerd Font missing and curl/unzip not available - install it from nerdfonts.com"
  fi
}

if [ "$do_packages" -eq 1 ]; then install_packages; install_font; fi
install_pokemon

# ---- copy configs ---------------------------------------------------------------
say "installing configs into $cfg"
run mkdir -p "$cfg"
for d in "$here"/config/*/; do
  name="$(basename "$d")"
  target="$cfg/$name"
  if [ -e "$target" ] || [ -L "$target" ]; then
    if [ "$do_backup" -eq 1 ]; then
      run mv "$target" "$target.bak-$stamp"; echo "   backup: $name -> $name.bak-$stamp"
    else
      run rm -rf "$target"
    fi
  fi
  run mkdir -p "$target"
  run cp -a "$d." "$target/" || die "could not copy $name to $target"
  # keep what the settings window saved (mouse, monitors, opacity, gaps, bar) across re-installs
  if [ "$name" = i3 ] && [ "$dry" -eq 0 ] && [ -f "$target.bak-$stamp/settings.json" ]; then
    cp -a "$target.bak-$stamp/settings.json" "$target/settings.json"
  fi
done

if [ "$dry" -eq 0 ]; then
  find "$cfg/i3/scripts" -type f \( -name '*.sh' -o -name '*.py' \) -exec chmod +x {} + 2>/dev/null || true
  chmod +x "$cfg/polybar/launch.sh" 2>/dev/null || true
fi
choose_terminal
install_shell_hook

# ---- wallpapers / folders ---------------------------------------------------------
run mkdir -p "$HOME/Pictures/wallpapers" "$HOME/Pictures/Screenshots"
if [ -d "$here/wallpapers" ]; then
  run cp -n "$here"/wallpapers/* "$HOME/Pictures/wallpapers/" 2>/dev/null || true
  say "copied bundled wallpapers to ~/Pictures/wallpapers"
fi
if [ "$do_wallpapers" -eq 1 ]; then
  command -v git >/dev/null 2>&1 || die "git is required for --wallpapers"
  say "downloading wallpaper bank (this can take a while)"
  tmp="$(mktemp -d)"
  if run git clone --depth=1 https://github.com/LinuxBeginnings/Wallpaper-Bank.git "$tmp/wb"; then
    run cp -n "$tmp"/wb/wallpapers/* "$HOME/Pictures/wallpapers/" 2>/dev/null || true
  else
    warn "wallpaper download failed"
  fi
  rm -rf "$tmp"
fi

# first login picks a wallpaper and generates colors
run rm -f "${XDG_CACHE_HOME:-$HOME/.cache}/i3/first-run-done"

# ---- sanity checks -----------------------------------------------------------------
if [ "$dry" -eq 0 ]; then
  for c in i3 polybar picom dunst rofi feh maim xdotool xclip i3lock brightnessctl pamixer playerctl notify-send xrandr xprop; do
    command -v "$c" >/dev/null 2>&1 || missing+=("$c")
  done
  command -v ghostty >/dev/null 2>&1 || command -v kitty >/dev/null 2>&1 || missing+=("a terminal (ghostty or kitty)")
  command -v clipmenu >/dev/null 2>&1 || command -v copyq >/dev/null 2>&1 || missing+=("clipmenu or copyq")
  if command -v i3 >/dev/null 2>&1; then
    ver="$(i3 --version 2>/dev/null | grep -o '[0-9]\+\.[0-9]\+' | head -n1)"
    if [ -n "$ver" ] && [ "$(printf '%s\n4.22\n' "$ver" | sort -V | head -n1)" != "4.22" ]; then
      warn "i3 $ver is older than 4.22 - the 'gaps' lines in the config need >= 4.22 (use a newer distro release or build i3)"
    fi
    if i3 -C -c "$cfg/i3/config" >/dev/null 2>&1; then say "i3 config validated OK"
    else warn "i3 rejected the config - see:  i3 -C -c ~/.config/i3/config"; fi
  fi
  [ -e /usr/share/xsessions/i3.desktop ] || warn "no 'i3' session file in /usr/share/xsessions - the login screen may not list i3"
  if [ "$FAMILY" = fedora ] && ! rpm -q xorg-x11-server-Xorg >/dev/null 2>&1; then
    warn "Xorg server is not installed - i3 cannot start without it:  sudo dnf install xorg-x11-server-Xorg"
  fi
fi

# ---- summary -------------------------------------------------------------------------
if [ "${#missing[@]}" -gt 0 ]; then
  echo
  warn "could not be installed automatically: $(printf '%s\n' "${missing[@]}" | sort -u | tr '\n' ' ')"
  warn "install them manually, or the matching keybinds/modules will do nothing (log: ~/.cache/i3wm-dots-install.log)"
fi

case "${XDG_CURRENT_DESKTOP:-}" in
  *GNOME*) how='GNOME: log out, click your name, then the gear icon (bottom-right) and choose "i3".' ;;
  *KDE*)   how='KDE: log out, then use the session menu at the login screen (bottom-left) and choose "i3".' ;;
  *)       how='Log out and choose the "i3" session at your login screen (or put "exec i3" in ~/.xinitrc).' ;;
esac
cat <<MSG

Done.  $how
  - SUPER+H shows every keybind.  SUPER+W picks a wallpaper.
  - SUPER+ALT+M opens Settings (mouse and cursor, monitors, window opacity, gaps, bar position/monitors).
  - Terminal: Ghostty (kitty if Ghostty could not be installed). Change it in ~/.config/i3/defaults.conf
  - Your old desktop is untouched - pick it again at the login screen any time.
  - Undo the dotfiles:  ./install.sh --restore
MSG
if [ "$FAMILY" = fedora ] && [ "${XDG_SESSION_TYPE:-}" = wayland ]; then
  cat <<'MSG'

Fedora note: recent Fedora releases moved GNOME to Wayland-only. If "i3" does not appear at the login
screen, your display manager may not offer X11 sessions. Switch to SDDM (or LightDM), which does:
    sudo dnf install sddm && sudo systemctl disable gdm && sudo systemctl enable sddm
MSG
fi
