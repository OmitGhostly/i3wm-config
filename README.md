# i3wm-config — monochrome i3 edition

## Quick start

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

## Repository layout

```
├── install.sh          installer (see options above)
├── config/             mirrors ~/.config
│   ├── i3/             i3 config, scripts/, rofi/, icons/, defaults.conf
│   ├── polybar/        bar (replaces Waybar)
│   ├── picom/          compositor: blur, rounded corners, shadows
│   ├── dunst/          notifications (replaces swaync)
│   ├── touchegg/       touchpad gestures (three-finger swipe = next / previous workspace)
│   ├── gtk-3.0/        dark GTK theme setting
│   └── ghostty/ kitty/ (28 colour themes) fastfetch/ (Pokémon greeting) cava/ swappy/
├── wallpapers/         four photos (night street lights is the first one you see)
├── tools/              make_blocks.py (writes config/polybar/blocks.ini, the block bar styles) and
│                       make_icons.py (draws the white volume, microphone and brightness icons in config/i3/icons)
└── LICENSE.md          GPL-3.0 (inherited from the original project)
```

## What replaced what

## Keybinds (highlights)

| Keys | Action |
|---|---|
| `SUPER+Return` / `SUPER+D` / `SUPER+E` | terminal / launcher / file manager |
| `SUPER+Q` | close window |
| `SUPER+Arrows` · `SUPER+CTRL+Arrows` · `SUPER+SHIFT+Arrows` | focus · move · resize |
| `SUPER+1…0` · `SUPER+SHIFT+1…0` | workspace · move window to workspace |
| `SUPER+F` · `SUPER+SPACE` | fullscreen · floating |
| `SUPER+ALT+1/2/3` | split / stacking / tabbed layout |
| `SUPER+ALT+T` | spiral tiling like Hyprland (default) ⇄ classic side by side |
| three fingers ← / → on the touchpad | next / previous workspace |
| `SUPER+SHIFT+Return` · `SUPER+U` | drop-down terminal · scratchpad |
| `SUPER+W` · `CTRL+ALT+W` | pick wallpaper · random wallpaper |
| `SUPER+SHIFT+S` · `SUPER+Print` | screenshot (annotate) · screenshot |
| `SUPER+ALT+V` · `SUPER+ALT+E` · `SUPER+ALT+C` | clipboard · emoji · calculator |
| `CTRL+ALT+L` · `CTRL+ALT+P` | lock · power menu |
| `SUPER+SHIFT+E` | quick settings (edit configs, reload, restart) |
| bar coffee button (click) | stay awake: no screen blanking, auto-lock or idle suspend until you click again or log out (`Caffeine.sh`) |

Everything else: `SUPER + H`. To add your own bind, edit `~/.config/i3/config` and put a `## description` line above it so it shows up in the cheat sheet.
Change your default terminal / file manager in `~/.config/i3/defaults.conf`.

