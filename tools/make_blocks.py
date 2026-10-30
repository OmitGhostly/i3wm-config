#!/usr/bin/env python3
"""Writes config/polybar/blocks.ini: the bar used by every bar style except Flat. Run it after changing an item's
format here:  python3 tools/make_blocks.py
Each item's colours, end glyphs and spacing come from style.ini ([barstyle] <item>-bg, -fg, -ul, -l, -lfg, -lbg,
-r, -rfg, -rbg, -gap), which the settings window writes for the chosen style each time the bar starts."""
import os

mods = [  # (module, [(format-name, format-string)], {extra key: value})
 ("playerctl", [("format", " <label> ")], {"label-foreground": "fg"}),
 ("network", [("format-connected", "%{A1:~/.config/i3/scripts/SettingsGUI.py --tab wifi:} <ramp-signal> <label-connected> %{A}"),
              ("format-disconnected", "%{A1:~/.config/i3/scripts/SettingsGUI.py --tab wifi:} <label-disconnected> %{A}")],
             {"label-disconnected-foreground": "fg"}),
 ("bluetooth", [("format", " <label> ")], {}),
 ("pulseaudio", [("format-volume", " <ramp-volume> <label-volume> "), ("format-muted", " <label-muted> ")],
                {"label-muted-foreground": "fg"}),
 ("backlight", [("format", " <label> ")], {}),
 ("caffeine", [("format", " <label> ")], {"label-foreground": "fg"}),
 ("nightlight", [("format", " <label> ")], {"label-foreground": "fg"}),
 ("battery", [("format-charging", " 󰂄 <label-charging> "), ("format-discharging", " <ramp-capacity> <label-discharging> "),
              ("format-full", " 󰁹 <label-full> "), ("format-low", " 󰂃 <label-low> ")], {"label-low-foreground": "fg"}),
 ("cpu", [("format", " <label> ")], {"label": "󰻠 %percentage:2%%"}),
 ("memory", [("format", " <label> ")], {"label": "󰍛 %percentage_used:2%%"}),
 ("gpu", [("format", " <label> ")], {}),
 ("date", [("format", " <label> ")], {"label-foreground": "fg"}),
 ("powermenu", [("format", " %{T2}󰐥%{T-} ")], {}),
]
out = ["; The bar for every style except Flat (Settings > Appearance > Bar style). Each item's colours, end glyphs and",
       "; spacing come from style.ini [barstyle], which the settings window writes for the chosen style when the bar",
       "; starts. Written by tools/make_blocks.py in the repository: change that and run it, rather than editing this.",
       "",
       "[bar/blocks]",
       "inherit = bar/main",
       "module-margin = 0",
       "; the power button's block reaches the screen edge, like the workspace block on the left",
       "padding-right = 0",
       "font-2 = ${env:BAR_CAP_SPEC:FantasqueSansM Nerd Font Mono:size=27.277;5}",
       "modules-right = ${env:BAR_RIGHT_B:" + " ".join("b-" + m for m, _f, _e in mods if m != "playerctl") + "}",
       ""]
for m, fmts, extra in mods:
    k = "${barstyle.%s-%%s}" % m
    bg, fg = k % "bg", k % "fg"
    out.append("[module/b-%s]" % m)
    out.append("inherit = module/%s" % m)
    for name, text in fmts:
        out += ['%s = "%s"' % (name, text),
                "%s-background = %s" % (name, bg),
                "%s-foreground = %s" % (name, fg),
                "%s-underline = %s" % (name, k % "ul"),
                "%s-prefix = %s" % (name, k % "l"),
                "%s-prefix-font = 3" % name,
                "%s-prefix-foreground = %s" % (name, k % "lfg"),
                "%s-prefix-background = %s" % (name, k % "lbg"),
                "%s-suffix = %s" % (name, k % "r"),
                "%s-suffix-font = 3" % name,
                "%s-suffix-foreground = %s" % (name, k % "rfg"),
                "%s-suffix-background = %s" % (name, k % "rbg"),
                "%s-margin = %s" % (name, k % "gap"),
                "%s-offset = %s" % (name, k % "lead")]
    for k, v in extra.items():
        out.append("%s = %s" % (k, fg if v == "fg" else v))
    out.append("")
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "polybar", "blocks.ini"), "w").write("\n".join(out))
print("wrote blocks.ini:", len(out), "lines")
