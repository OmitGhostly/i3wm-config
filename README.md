# i3wm-config — monochrome i3 edition

An **i3wm (X11)** port of [LinuxBeginnings/Hyprland-Dots](https://github.com/LinuxBeginnings/Hyprland-Dots).
Hyprland is a Wayland compositor, so every Wayland-only piece was swapped for an X11 equivalent while keeping
the keybinds, and restyled as a **simple, sleek black & white** desktop: flat white-on-black polybar with roman-numeral
workspaces, chunky borders and gaps, monochrome rofi / dunst / kitty / ghostty / cava, grayscale wallpapers (or pick any accent colour in Settings > Colors), and a
**Pokémon fastfetch** greeting in every new **Ghostty** (or kitty) window. Ghostty is the default terminal; kitty is the automatic fallback.

**Design & tools** follow [addy-dclxvi/i3-starterpack](https://github.com/addy-dclxvi/i3-starterpack) (gaps, thick borders, roman workspaces),
[TheDistroHopper/i3wm-nord](https://github.com/TheDistroHopper/i3wm-nord) and [traumachan7219-collab/i3-dots](https://github.com/traumachan7219-collab/i3-dots)
(i3 + polybar + picom + rofi + dunst + kitty + feh + i3lock), recolored to pure monochrome. The keybinds follow the original (`SUPER+H` lists them) and can be changed in the Settings window (`SUPER+ALT+M`, Keybindings tab).

![preview](docs/preview.png)

## Quick start

Works from a **KDE or GNOME** desktop (or anything else): the installer adds i3 and Xorg *next to* your current desktop,
so you keep both and pick one at the login screen. Primary target: **Fedora**; also Arch-based and Debian/Ubuntu-based systems.

```bash
git clone https://github.com/OmitGhostly/i3wm-config.git
cd i3wm-config
chmod +x install.sh
./install.sh
```

Or without cloning:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/OmitGhostly/i3wm-config/main/install.sh)
```

Then log out and choose the **i3** session (GNOME: gear icon on the login screen; KDE: session menu, bottom-left).
Press **`SUPER + H`** for the full keybind list. Do not run it with `sudo` - it asks for your password only when installing packages.

### Installer options

| Option | What it does |
|---|---|
| *(none)* | Install i3 + all dependencies, then the dotfiles |
| `--no-packages` | Only copy the dotfiles (you already have the programs) |
| `--no-ghostty` | Don't install Ghostty (kitty is used as the terminal) |
| `--no-pokemon` | Don't clone pokescript (a bundled shiny Mimikyu sprite is used) |
| `--wallpapers` | Also download the full KooL wallpaper bank into `~/Pictures/wallpapers` |
| `--no-backup` | Overwrite existing configs instead of moving them aside |
| `--restore` | Put back the newest `*.bak-*` backups and exit |
| `--dry-run` | Print what would happen without changing anything |

Existing folders in `~/.config` that the installer replaces are moved to `<name>.bak-<timestamp>` (only the first time; later re-installs overwrite the earlier install instead of making new backups).
Every run is logged to `~/.cache/i3wm-dots-install.log` - attach it when reporting a problem.
Each package is checked against your distro's repos before installing, so one missing name never aborts the rest;
anything that could not be installed is listed at the end.

### Fedora notes

- **Xorg is required.** The installer adds `xorg-x11-server-Xorg`. i3 is an X11 window manager; it runs as its own login session even if your GNOME/KDE session is Wayland.
- **Login screen:** if "i3" is missing from the session list, your display manager may not offer X11 sessions (recent Fedora releases moved GNOME to Wayland-only). SDDM and LightDM do:
  `sudo dnf install sddm && sudo systemctl disable gdm && sudo systemctl enable sddm`
- **Ghostty** has no official Fedora package, so the installer enables the community COPR `pgdev/ghostty` and installs it from there (use `--no-ghostty` to skip). If that fails, kitty is used automatically. On Debian/Ubuntu Ghostty has no repo package, so kitty is used.
- **clipmenu** is not in Fedora's repos, so the installer uses **CopyQ** instead (same keybind, `SUPER+ALT+V`).
- **Pokémon fastfetch:** the greeting always shows a **shiny Mimikyu** from [acxz/pokescript](https://github.com/acxz/pokescript) next to `fastfetch` system info. The installer clones pokescript to `~/.local/share/pokescript` (a copy of the sprite also ships in `~/.config/fastfetch/` as a fallback; MIT licence, see `POKESCRIPT-LICENSE.txt`). The greeting only runs inside Ghostty or kitty. Skip it with `--no-pokemon`.

- **FantasqueSansM Nerd Font** (bar/terminal icons) is downloaded to `~/.local/share/fonts` if missing.
- Requires **i3 >= 4.22** (`gaps` are built in); current Fedora releases ship newer.

![greeting](docs/pokemon-greeting.png)

## Updating

`sudo dnf upgrade` updates the *programs* (i3, polybar, picom, rofi, ...) but never touches your configs in `~/.config`, so your setup stays as it is. To get newer versions of these dotfiles, `git pull` and re-run `./install.sh --no-packages`: your original configs stay backed up as `*.bak-<timestamp>` (re-installs replace the previous install without piling up more backups, so `--restore` always returns your original setup) and your `~/.config/i3/settings.json` (Settings window choices) is kept.

## Security notes

- Everything runs as your user; only the package install step uses `sudo`, and only for your package manager.
- Settings are validated before use: every value in `settings.json` is type- and range-checked when it is loaded (key combos, application commands, cursor and theme names, colours, monitor modes, positions, opacity and gaps), and the i3 config is tested with `i3 -C` before new keybindings are reloaded. Anything malformed is dropped and the default used, so a corrupt or hand-edited file can never crash the window or reach a config file. Config files are written atomically (a crash mid-write never leaves half a file).
- Menus that run things you pick (SSH hosts, music links, zsh themes) pass the choice as a plain argument, never through a shell, and refuse names that look like options.
- Third-party sources the installer can pull from: the `pgdev/ghostty` COPR (Fedora), the FantasqueSansM Nerd Font release download (not checksum-pinned), and acxz/pokescript (pinned to a fixed commit). Skip them with `--no-ghostty`, `--no-pokemon` or by installing the font yourself. Read `install.sh` before running it, as with any script you pipe from the internet.

## Troubleshooting

- No bar or wrong monitors: run `~/.config/polybar/launch.sh`; logs are in `$XDG_RUNTIME_DIR/polybar-<monitor>.log`.
- A keybind stopped working after editing: `i3 -C -c ~/.config/i3/config` shows the error; Keybindings > *Reset all to default* restores the shipped binds.
- Windows stacked as tabs instead of side by side: press `SUPER+ALT+1` (side by side); `SUPER+ALT+2/3` and `SUPER+G` switch to stacked/tabbed on purpose. New windows always open side by side by default.
- Mimikyu greeting shows twice: another line in `~/.zshrc` or `~/.bashrc` also prints a greeting. Find it with `grep -n 'fastfetch\|PokeFetch\|pokemon' ~/.zshrc ~/.bashrc` and delete the line that isn't marked `# i3wm-dots`. Re-running the installer leaves exactly one of ours.
- No transparency, shadows or blur: the compositor could not use your GPU (common in virtual machines); `Picom.sh` then falls back to picom's software backend automatically. Toggle the compositor with `SUPER+ALT+O`.
- i3 itself froze or crashed: i3 shows a prompt to restart it in place (your windows stay open). Keep i3 up to date: 4.24 and 4.25 fixed several crashes (Debian/Ubuntu still ship 4.23).
- Install problems: attach `~/.cache/i3wm-dots-install.log`; `./install.sh --restore` brings back your old configs.

## Compatibility

Checked against the real tools, not only the docs:

| Tool | Check | Result |
|---|---|---|
| i3 4.23 | `i3 -C` config validation (all 152 binds, window rules, autostart) | passes |
| Polybar 3.7 | bar starts with all modules; i3 reserves the bar's space (workspace starts below the bar) | passes |
| picom 10 | starts with the shipped config; Fedora ships picom 13 (same options) | passes |
| dunst 1.9 | config parses without warnings (older-syntax values chosen for compatibility) | passes |
| rofi 1.7.5 | all 41 shipped `.rasi` themes/configs parse | passes |
| Scripts | `bash -n` + `shellcheck` clean; screenshot, wallpaper, reload, compositor toggle ran in a virtual X server | passes |

Fixed along the way: Polybar's `override-redirect` made i3 ignore the bar's reserved space (windows tiled underneath it) - removed.
Polybar, picom and pamixer are in Fedora 43/44 repos (confirmed on packages.fedoraproject.org).
**Not yet tested on real hardware:** Ghostty itself (it could not be installed in the test environment; the terminal key, drop-down terminal and fallback logic were tested with a stand-in), dunst running (needs a desktop D-Bus session), lock screen, touchpad / brightness / media keys, multi-monitor, and a real `dnf` run.

## Settings window

Press `SUPER+ALT+M` (or run `~/.config/i3/scripts/SettingsGUI.py`). Changes are applied immediately and saved to `~/.config/i3/settings.json`, which is re-applied at every login.

- **Mouse:** pick a device (or all mice and touchpads), set pointer speed, and turn acceleration on or off. A **Mouse cursor** section below picks the cursor theme and size (with a preview). It sets `~/.icons/default`, Xresources and GTK, so it applies to newly opened programs.
- **Displays:** a Windows-style layout grid. Drag the numbered screens to match your desk; they snap to each other's edges. Click a screen to set its resolution, refresh rate, orientation (landscape, portrait, flipped), **scale** (100-300%; makes everything bigger on that screen, done with `xrandr --scale`, so values above 100% look slightly softer than native), enable/disable it, or make it primary. **Identify** flashes each screen's number on that monitor.
- **Appearance:** sliders for the opacity of the focused window, of unfocused windows and of the **terminal background** (20-100%; the terminal slider writes `background-opacity` for Ghostty and `background_opacity` for kitty and reloads them live, so only the terminal's background turns see-through). Writes `active-opacity` / `inactive-opacity` in `~/.config/picom/picom.conf` and restarts picom. Needs the compositor running. The same tab sets the **gaps** between windows and around the screen edge (0-40 px) and whether a lone window gets no gaps; these are written to `gaps inner` / `gaps outer` / `smart_gaps` in `~/.config/i3/config`. A **Bar** section sets the bar's position (top or bottom; left/right is not possible with Polybar), its **size** (Normal / Large / Extra large: taller bar and bigger text, Large is the default for sharper text) and which monitors show it (all, or only the ones you tick, numbered like the Displays tab).
- **Colors:** choose the accent colour of the whole setup - *Mono* (the default white), Cyan, Blue, Green, Purple, Pink, Red, Orange, Yellow, or any custom `#rrggbb` (too-dark colours are refused because they would be unreadable on black). It recolours window borders, the bar, rofi menus, notifications, the lock screen, the stay-awake button, the audio visualizer, the terminal greeting and the Settings window itself. Black and the greys stay. The choice is saved and re-applied at every login (also after re-installing). Terminal *palettes* are separate: use the Themes tab.
- **Themes:** pick a colour theme for **Ghostty** and for **kitty** from searchable lists, with a live preview of the background, text and the 16 terminal colours. Ghostty lists its built-in themes plus the ones in `~/.config/ghostty/themes`; kitty lists the bundled `kitty-themes`. Apply writes `theme = ...` (Ghostty) or the `include .../kitty-themes/NAME.conf` line (kitty) and reloads open terminals. *Monochrome (default)* is the shipped black & white theme.
- **Keybindings:** every keybind with its description and a search box. Pick one, press **Change key...** and press the new combination (it can record combos i3 normally swallows, like `SUPER+Return`). If the combo is already used you can swap the two. Applying checks the result with `i3 -C`, writes it into `~/.config/i3/config` and reloads i3; **Reset** puts keys back. Rows for the **file manager, terminal and browser** show the program in brackets, e.g. `file manager (Dolphin)`; **Change application...** lists the installed alternatives (or any command you type) and saves the choice to `~/.config/i3/defaults.conf`. Your changes are remembered in `settings.json` and re-applied after a reinstall or update of the config.
- **Bluetooth:** a power switch, the list of your paired devices (Connect / Disconnect / Forget), and **Add a device**: put the device in pairing mode, press *Search for devices*, pick it and press *Pair and connect*. It uses `bluetoothctl` (BlueZ; the installer sets up the service). Devices that need a PIN (some keyboards) can be paired with the *Open full Bluetooth manager* button (Blueman).
- **Wi-Fi:** a power switch, the networks in range (signal, security, saved/connected), Connect (asks for the password the first time; open and remembered networks just connect), Disconnect, Forget network, Scan again, and *Join a hidden network...*. It uses NetworkManager (`nmcli`). The password is passed to `nmcli` on its command line for a moment while joining, so other users on a shared computer could see it in the process list; use the full network editor (`nm-connection-editor`) there. Work/school logins (802.1X) also need the full editor.
- After applying display changes you get 10 seconds to press **Keep**; if the screen goes dark, wait and the old layout is restored.

![mouse](docs/settings-mouse.png)
![displays](docs/settings-displays.png)
![dragging a screen](docs/settings-displays-drag.png)
![appearance](docs/settings-appearance.png)
![colors](docs/settings-colors.png)

![themes](docs/settings-themes.png)
![keybindings](docs/settings-keybinds.png)
![bluetooth](docs/settings-bluetooth.png)
![wifi](docs/settings-wifi.png)

## Repository layout

```
├── install.sh          installer (see options above)
├── config/             mirrors ~/.config
│   ├── i3/             i3 config, scripts/, rofi/, icons/, defaults.conf
│   ├── polybar/        bar (replaces Waybar)
│   ├── picom/          compositor: blur, rounded corners, shadows
│   ├── dunst/          notifications (replaces swaync)
│   └── kitty/ ghostty/ wezterm/ starship/ fastfetch/ (Pokémon greeting) btop/ yazi/ cava/ Kvantum/ qt5ct/ qt6ct/ swappy/
├── wallpapers/         a few starter wallpapers
└── LICENSE.md          GPL-3.0 (inherited from the original project)
```

## What replaced what

| Hyprland dots | This port |
|---|---|
| Hyprland config (Lua) | `config/i3/config` — 152 keybinds, window rules, autostart |
| Waybar | Polybar (one bar per monitor, tray on primary) |
| swaync | dunst — `SUPER+SHIFT+N` shows history |
| Hyprland blur / rounding / shadow / dim | picom |
| swww / awww | feh (`Wallpaper.sh`) |
| hyprlock / hypridle | i3lock(-color) + xss-lock + `xset dpms` |
| wlogout | rofi power menu (`Powermenu.sh`) |
| nwg-displays / mouse settings | `SUPER+ALT+M` settings window (`SettingsGUI.py`) |
| grim / slurp | maim + xdotool + xclip |
| wl-copy / cliphist | xclip / clipmenu (CopyQ on Fedora) |
| hyprsunset | redshift (`Nightlight.sh`) |
| `[input]` block | `Input.sh` (setxkbmap / xset / xinput) |
| Special workspace | i3 scratchpad |
| Window groups | i3 tabbed / stacked containers |
| Quickshell / AGS overview | rofi window switcher (`SUPER+A`) |

## Keybinds (highlights)

| Keys | Action |
|---|---|
| `SUPER+Return` / `SUPER+D` / `SUPER+E` | terminal / launcher / file manager |
| `SUPER+Q` | close window |
| `SUPER+Arrows` · `SUPER+CTRL+Arrows` · `SUPER+SHIFT+Arrows` | focus · move · resize |
| `SUPER+1…0` · `SUPER+SHIFT+1…0` | workspace · move window to workspace |
| `SUPER+F` · `SUPER+SPACE` | fullscreen · floating |
| `SUPER+ALT+1/2/3` | split / stacking / tabbed layout |
| `SUPER+SHIFT+Return` · `SUPER+U` | drop-down terminal · scratchpad |
| `SUPER+W` · `CTRL+ALT+W` | pick wallpaper · random wallpaper |
| `SUPER+SHIFT+S` · `SUPER+Print` | screenshot (annotate) · screenshot |
| `SUPER+ALT+V` · `SUPER+ALT+E` · `SUPER+ALT+C` | clipboard · emoji · calculator |
| `CTRL+ALT+L` · `CTRL+ALT+P` | lock · power menu |
| `SUPER+SHIFT+E` | quick settings (edit configs, reload, restart) |
| bar coffee button (click) | stay awake: no screen blanking, auto-lock or idle suspend until you click again or log out (`Caffeine.sh`) |

Everything else: `SUPER + H`. To add your own bind, edit `~/.config/i3/config` and put a `## description` line above it so it shows up in the cheat sheet.
Change your default terminal / file manager in `~/.config/i3/defaults.conf`.

## Not ported (Hyprland/Wayland-specific)

Animation menus and presets, the dwindle/master/scrolling layout switcher, rainbow borders, the Hyprview/Quickshell/AGS overviews,
the monitor-profile manager (use `arandr`, `SUPER+ALT+D`), Waybar style/layout menus, hyprlock themes, Hyprland portal scripts,
and the original distro installers (`copy.sh`, `Distro-Hyprland.sh`, dots-tui).

## Dependencies

`i3 (≥4.22) xorg polybar picom dunst rofi ghostty|kitty feh maim xdotool xclip xss-lock i3lock imagemagick brightnessctl pamixer playerctl pavucontrol nm-applet redshift clipmenu|copyq numlockx xinput xrandr xprop xdpyinfo setxkbmap libnotify mpv qalc jq curl arandr thunar lxappearance fastfetch bluez blueman`
· optional: `pokescript` (cloned by the installer), `swappy`/`flameshot`, `i3lock-color`, `polkit-gnome`, *FantasqueSansM Nerd Font*.

## Credits & license

All configs, themes and most scripts originate from **[LinuxBeginnings/Hyprland-Dots](https://github.com/LinuxBeginnings/Hyprland-Dots)** (KooL Dots) — thank you to the original author and contributors.
This port is distributed under the same **GPL-3.0-or-later** license.
