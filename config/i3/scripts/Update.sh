#!/usr/bin/env bash
# Keep the desktop config (i3, bar, Settings window...) up to date with the GitHub repo.
#
# After a system update (sudo pacman -Syu on Arch, sudo dnf upgrade on Fedora, apt upgrade on Debian/Ubuntu) a
# small system hook asks your session to run this. It fetches the newest version of the repo into a private copy
# (~/.local/share/i3wm-dots-updater/repo) and, only when something changed, re-installs the config files the quick
# way (install.sh --update: no packages, no password). What you set in the Settings window (colours, bar style,
# keybindings, mouse, monitors...) is kept; files you edited by hand in ~/.config/i3, polybar, ... are replaced -
# the version before the update is kept, and "i3dots-update --undo" puts it back.
# If you were not logged in during the system update, it runs at your next login instead.
#
#   i3dots-update                 update now (also works when automatic updates are off)
#   i3dots-update --check         only say whether there is a newer version
#   i3dots-update --undo          go back to the config from before the last update
#   i3dots-update --off / --on    turn the automatic updates off / on again
#   i3dots-update --status        show the settings and the last update
#   i3dots-update --install-hook  set up the pacman / dnf / apt hook (asks for your password once)
#   i3dots-update --remove-hook   take it away again
#   (--auto and --login are what the hook and i3 use)
set -uo pipefail

cfg="${XDG_CONFIG_HOME:-$HOME/.config}"
state="${XDG_DATA_HOME:-$HOME/.local/share}/i3wm-dots-updater"
repo="$state/repo"
log="${XDG_CACHE_HOME:-$HOME/.cache}/i3wm-dots-update.log"
default_url="https://github.com/OmitGhostly/i3wm-config.git"
# system files (I3DOTS_TEST_ROOT puts them in a test folder instead, without sudo)
root="${I3DOTS_TEST_ROOT:-}"
hook_bin="$root/usr/local/lib/i3wm-dots/system-updated"
users_file="$root/etc/i3wm-dots/users"
sys_stamp="$root/var/lib/i3wm-dots/last-system-update"
pacman_hook="$root/etc/pacman.d/hooks/i3wm-dots.hook"
dnf5_action="$root/etc/dnf/libdnf5-plugins/actions.d/i3wm-dots.actions"
dnf4_action="$root/etc/dnf/plugins/post-transaction-actions.d/i3wm-dots.action"
apt_hook="$root/etc/apt/apt.conf.d/99i3wm-dots"

mode="${1:-now}"
quiet=0
case "$mode" in --auto|--login) quiet=1 ;; esac

say() { if [ "$quiet" -eq 1 ]; then printf '%s %s\n' "$(date '+%F %T')" "$*" >>"$log"; else printf '%s\n' "$*"; fi; }
note() { command -v notify-send >/dev/null 2>&1 && notify-send -a "i3wm-dots" -u low "$@" 2>/dev/null; true; }

if [ "$(id -u)" -eq 0 ] && [ -z "$root" ]; then
  echo "run this as your normal user, not root" >&2
  exit 1
fi
mkdir -p "$state" "$(dirname "$log")"
if [ "$quiet" -eq 1 ] && [ -f "$log" ] && [ "$(wc -l <"$log")" -gt 1000 ]; then
  tail -n 500 "$log" >"$log.tmp" && mv "$log.tmp" "$log"          # keep the log small
fi

# where to get updates: the repo this desktop was installed from (written by install.sh). An ssh address is
# turned into https: the update runs in the background, where no ssh key password can be typed.
repo_url() {
  local u
  u="$(head -n1 "$state/repo-url" 2>/dev/null)"
  case "$u" in
    git@github.com:*) u="https://github.com/${u#git@github.com:}" ;;
    https://*|file://*|/*) ;;
    *) u="$default_url" ;;
  esac
  printf '%s\n' "$u"
}

# ------------------------------------------------------------------ the system hook (pacman / dnf / apt)
as_root() { if [ -n "$root" ] || [ "$(id -u)" -eq 0 ]; then "$@"; else sudo "$@"; fi; }
put_root_file() {   # put_root_file PATH MODE  (content on stdin)
  as_root mkdir -p "$(dirname "$1")" && as_root tee "$1" >/dev/null && as_root chmod "$2" "$1"
}

hook_script() {
  cat <<'EOF'
#!/bin/sh
# i3wm-dots: runs (as root) after pacman / dnf / apt has installed or updated packages. It changes nothing
# itself: it notes the time, then asks the session of each user listed in /etc/i3wm-dots/users to check GitHub
# for a newer desktop config (their own ~/.config/i3/scripts/Update.sh, run as that user).
# A user who is not logged in right now gets the update at their next login.
dir="$(dirname "$0")/../../../.."
mkdir -p "$dir/var/lib/i3wm-dots" 2>/dev/null && date +%s >"$dir/var/lib/i3wm-dots/last-system-update" 2>/dev/null
chmod 644 "$dir/var/lib/i3wm-dots/last-system-update" 2>/dev/null
[ -r "$dir/etc/i3wm-dots/users" ] || exit 0
while read -r u; do
  case "$u" in ''|-*|*[!A-Za-z0-9._-]*) continue ;; esac
  uid="$(id -u "$u" 2>/dev/null)" || continue
  bus="/run/user/$uid/bus"
  [ -S "$bus" ] || continue
  runuser -u "$u" -- env XDG_RUNTIME_DIR="/run/user/$uid" DBUS_SESSION_BUS_ADDRESS="unix:path=$bus" \
    systemctl --user start --no-block i3dots-update.service >/dev/null 2>&1 || true
done <"$dir/etc/i3wm-dots/users"
exit 0
EOF
}

install_hook() {
  local me found=0
  me="$(id -un)"
  echo "Setting up the system hook (asks for your password once)..."
  hook_script | put_root_file "$hook_bin" 755 || { echo "could not write $hook_bin" >&2; return 1; }
  as_root mkdir -p "$(dirname "$users_file")" "$(dirname "$sys_stamp")"
  if ! grep -qxF "$me" "$users_file" 2>/dev/null; then
    printf '%s\n' "$me" | as_root tee -a "$users_file" >/dev/null
  fi
  as_root chmod 644 "$users_file"
  if command -v pacman >/dev/null 2>&1 || [ -n "$root" ]; then
    put_root_file "$pacman_hook" 644 <<EOF
# i3wm-dots: after pacman installs or updates packages (e.g. sudo pacman -Syu), also update the desktop config
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = *

[Action]
Description = Asking i3wm-dots to check GitHub for a newer desktop config...
When = PostTransaction
Exec = /usr/local/lib/i3wm-dots/system-updated
EOF
    echo "  pacman: $pacman_hook"; found=1
  fi
  if command -v dnf5 >/dev/null 2>&1 || { command -v dnf >/dev/null 2>&1 && dnf --version 2>/dev/null | grep -qi dnf5; } || [ -n "$root" ]; then
    if [ -z "$root" ] && ! rpm -q libdnf5-plugin-actions >/dev/null 2>&1; then
      as_root dnf install -y libdnf5-plugin-actions || echo "  could not install libdnf5-plugin-actions (dnf's actions plugin)" >&2
    fi
    put_root_file "$dnf5_action" 644 <<EOF
# i3wm-dots: after dnf installs or updates packages (e.g. sudo dnf upgrade), also update the desktop config
post_transaction::::/usr/local/lib/i3wm-dots/system-updated
EOF
    echo "  dnf: $dnf5_action"; found=1
  elif command -v dnf >/dev/null 2>&1; then           # older Fedora (dnf 4)
    rpm -q python3-dnf-plugin-post-transaction-actions >/dev/null 2>&1 \
      || as_root dnf install -y python3-dnf-plugin-post-transaction-actions \
      || echo "  could not install python3-dnf-plugin-post-transaction-actions" >&2
    put_root_file "$dnf4_action" 644 <<EOF
# i3wm-dots: after dnf installs or updates packages, also update the desktop config
*:any:/usr/local/lib/i3wm-dots/system-updated
EOF
    echo "  dnf (4): $dnf4_action"; found=1
  fi
  if command -v apt-get >/dev/null 2>&1 || [ -n "$root" ]; then
    put_root_file "$apt_hook" 644 <<EOF
// i3wm-dots: after apt installs or updates packages, also update the desktop config
DPkg::Post-Invoke { "if [ -x /usr/local/lib/i3wm-dots/system-updated ]; then /usr/local/lib/i3wm-dots/system-updated || true; fi"; };
EOF
    echo "  apt: $apt_hook"; found=1
  fi
  [ "$found" -eq 1 ] || echo "  no pacman, dnf or apt found: updates then only run when you type i3dots-update"
  echo "Done: from now on a system update also checks GitHub for a newer desktop config."
}

remove_hook() {
  local me rest
  me="$(id -un)"
  if [ -f "$users_file" ]; then
    rest="$(grep -vxF "$me" "$users_file" || true)"
    if [ -n "$rest" ]; then printf '%s\n' "$rest" | put_root_file "$users_file" 644
    else as_root rm -f "$users_file"; fi
  fi
  if [ ! -s "$users_file" ]; then          # nobody else uses it: take the hook away completely
    as_root rm -f "$hook_bin" "$pacman_hook" "$dnf5_action" "$dnf4_action" "$apt_hook" "$sys_stamp"
  fi
  echo "The system hook no longer updates your desktop config (i3dots-update still works by hand)."
}

# ------------------------------------------------------------------ the update itself
fetch() {   # bring the private copy of the repo up to date; prints the newest commit
  local url
  url="$(repo_url)"
  command -v git >/dev/null 2>&1 || { say "git is not installed" >&2; return 1; }
  export GIT_TERMINAL_PROMPT=0
  if [ -d "$repo/.git" ] && [ "$(git -C "$repo" remote get-url origin 2>/dev/null)" = "$url" ]; then
    timeout 120 git -C "$repo" fetch -q --depth 1 origin HEAD >/dev/null 2>&1 || { say "could not reach $url" >&2; return 1; }
  else
    rm -rf "$repo"
    timeout 300 git clone -q --depth 1 "$url" "$repo" >/dev/null 2>&1 || { rm -rf "$repo"; say "could not download $url" >&2; return 1; }
    git -C "$repo" fetch -q --depth 1 origin HEAD >/dev/null 2>&1 || true
  fi
  git -C "$repo" rev-parse FETCH_HEAD 2>/dev/null || git -C "$repo" rev-parse HEAD
}

reload_desktop() {
  command -v i3-msg >/dev/null 2>&1 && i3-msg -q reload >/dev/null 2>&1 || true   # (also restarts the bar)
}

update() {
  if [ ! -f "$cfg/i3/.i3wm-dots-installed" ]; then
    say "the i3 config in $cfg/i3 was not installed by i3wm-dots - nothing to update"
    return 0
  fi
  local new old subject
  new="$(fetch)" || return 1
  old="$(cat "$state/applied" 2>/dev/null)"
  if [ -n "$new" ] && [ "$new" = "$old" ]; then
    say "already up to date (${new:0:7})"
    date +%s >"$state/last-run"
    return 0
  fi
  git -C "$repo" reset -q --hard "$new" || { say "could not use the downloaded version"; return 1; }
  [ -f "$repo/install.sh" ] && [ -f "$repo/config/i3/config" ] || { say "the download does not look like i3wm-dots"; return 1; }
  # keep the current version, for --undo
  rm -rf "$state/previous.tmp" && mkdir -p "$state/previous.tmp"
  local d name
  for d in "$repo"/config/*/; do
    name="$(basename "$d")"
    [ -e "$cfg/$name" ] && cp -a "$cfg/$name" "$state/previous.tmp/$name"
  done
  rm -rf "$state/previous" && mv "$state/previous.tmp" "$state/previous"
  subject="$(git -C "$repo" log -1 --format=%s 2>/dev/null)"
  say "updating to ${new:0:7}: $subject"
  if ! bash "$repo/install.sh" --update >>"$log" 2>&1; then
    say "the update failed (see $log) - putting the previous version back"
    undo >/dev/null
    note "Desktop config update failed" "Your previous config was put back. Details: $log"
    return 1
  fi
  printf '%s\n' "$new" >"$state/applied"
  date +%s >"$state/last-run"
  reload_desktop
  say "updated to ${new:0:7}"
  note "Desktop config updated" "${subject:-new version} (${new:0:7}). Undo: i3dots-update --undo"
  return 0
}

undo() {
  [ -d "$state/previous" ] || { echo "nothing to undo (no update has replaced your config yet)"; return 1; }
  local d name
  for d in "$state/previous"/*/; do
    name="$(basename "$d")"
    rm -rf "${cfg:?}/$name" && cp -a "$d" "$cfg/$name"
  done
  rm -f "$state/applied"          # the next update installs the newest version again
  reload_desktop
  echo "put back the config from before the last update"
}

auto_on() { [ ! -f "$state/off" ]; }

# ------------------------------------------------------------------ commands
exec 9>"$state/lock"
case "$mode" in
  --install-hook) install_hook; exit $? ;;
  --remove-hook)  remove_hook; exit $? ;;
  --off)    : >"$state/off"; echo "automatic updates are off (i3dots-update still updates by hand)"; exit 0 ;;
  --on)     rm -f "$state/off"; echo "automatic updates are on"; exit 0 ;;
  --status)
    echo "automatic updates: $(auto_on && echo on || echo off)"
    echo "repo:              $(repo_url)"
    a="$(cat "$state/applied" 2>/dev/null)"; echo "installed version: ${a:0:7}${a:+ }$( [ -n "$a" ] && git -C "$repo" log -1 --format='(%cd) %s' --date=short "$a" 2>/dev/null)"
    [ -f "$state/last-run" ] && echo "last check:        $(date -d "@$(cat "$state/last-run")" '+%F %H:%M' 2>/dev/null)"
    if [ -x "$hook_bin" ] && grep -qxF "$(id -un)" "$users_file" 2>/dev/null; then echo "system hook:       set up"
    else echo "system hook:       not set up (run: i3dots-update --install-hook)"; fi
    exit 0 ;;
  --check)
    flock -w 300 9 || exit 1
    new="$(fetch)" || exit 1
    if [ "$new" = "$(cat "$state/applied" 2>/dev/null)" ]; then echo "up to date (${new:0:7})"
    else echo "a newer version is available: ${new:0:7} $(git -C "$repo" log -1 --format=%s FETCH_HEAD 2>/dev/null)"; fi
    exit 0 ;;
  --undo)   flock -w 300 9 || exit 1; undo; exit $? ;;
  --auto)
    auto_on || { say "automatic updates are off"; exit 0; }
    flock -n 9 || exit 0            # one is already running
    update; exit $? ;;
  --login)
    # catch up on a system update that happened while you were logged out
    auto_on || exit 0
    sys="$(cat "$sys_stamp" 2>/dev/null)"; last="$(cat "$state/last-run" 2>/dev/null)"
    case "$sys" in ''|*[!0-9]*) exit 0 ;; esac
    case "$last" in ''|*[!0-9]*) last=0 ;; esac
    [ "$sys" -gt "$last" ] || exit 0
    sleep "${I3DOTS_LOGIN_DELAY:-20}"  # let the network come up first
    flock -n 9 || exit 0
    update; exit $? ;;
  now|--now)
    flock -w 300 9 || { echo "another update is running"; exit 1; }
    update; exit $? ;;
  -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
  *) echo "unknown option: $mode (try --help)" >&2; exit 2 ;;
esac
