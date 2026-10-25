"""Generic theme engine for the SigmaOS theme family
(SigmaOS-theme-color/cursor/icon/y/gtk3/desktop-environment/mdm/sync/
support/theming-native - inspired by mint-y, mint-themes, aether).

One engine, many repos: it understands theme indexes (index.theme INI),
role palettes, icon inheritance, settings application plans, theme sync
plans and theme diffs. Everything is pure planning/validation; nothing
writes into the user's session unless a caller wires the plan up itself.
"""
import argparse, hashlib, json, math, os, re, sys

ENGINE = {
    "name": "sigma-theme",
    "summary": "Generic theme engine: palettes, inheritance, sync and diffs",
    "language": "python",
    "verbs": ["list", "apply-plan", "sync-plan", "palette", "cursor",
              "icons", "diff"],
    "principles": ["Abstraction", "Generalisation", "Plan Before Act",
                   "Fail-Fast", "Defensive Programming", "DRY", "KISS",
                   "Deterministic Testing"],
}

cli_doc = """\
$ sigma-theme list --root ~/.themes
Mint-Y      Mint-Y      Standard dark-neutral theme
Mint-Y-Dark Mint-Y-Dark Dark variant
$ sigma-theme apply-plan --root ~/.themes --set gtk-theme=Mint-Y-Dark --set cursor-size=32
gsettings set org.gnome.desktop.interface gtk-theme 'Mint-Y-Dark'
$ sigma-theme palette ./A --compare ./B
changed bg: #1e1e2e -> #181825 (delta 12)
$ sigma-theme icons Mint-Y-Dark --root ~/.themes
Mint-Y-Dark inherits: Mint-Y, Adwaita  [ok]
$ sigma-theme sync-plan ./src/theme ./build/theme
$ sigma-theme diff ./A ./B
"""

_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
_ROLE_RE = re.compile(r"^[a-z0-9_.-]+$")
_SETTING_ORDER = ("gtk-theme", "icon-theme", "cursor-theme", "cursor-size",
                  "font", "font-size", "prefer-dark")
_NAME_SETTINGS = ("gtk-theme", "icon-theme", "cursor-theme")
_SCHEMA = {"gtk-theme": "org.gnome.desktop.interface",
           "icon-theme": "org.gnome.desktop.interface",
           "cursor-theme": "org.gnome.desktop.interface",
           "cursor-size": "org.gnome.desktop.interface",
           "font": "org.gnome.desktop.interface",
           "font-size": "org.gnome.desktop.interface",
           "prefer-dark": "org.gnome.desktop.color-scheme"}
_BASE_INHERITS = {"hicolor", "Adwaita", "gnome"}


class ThemeError(ValueError):
    pass


def _read(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _norm_hex(value):
    v = value.lower()
    if len(v) == 4:  # #abc -> #aabbcc
        return "#" + "".join(c * 2 for c in v[1:])
    return v


def parse_index(text):
    """Parse INI-style index.theme into {section: {key: value}}."""
    sections, cur = {}, None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            if not cur:
                raise ThemeError(f"line {lineno}: empty section name")
            sections.setdefault(cur, {})
            continue
        if "=" not in line:
            raise ThemeError(f"line {lineno}: cannot parse {line!r}")
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            raise ThemeError(f"line {lineno}: empty key")
        if key in sections.setdefault(cur or "default", {}):
            raise ThemeError(f"line {lineno}: duplicate key {key!r}")
        sections[cur or "default"][key] = value.strip()
    if not sections:
        raise ThemeError("empty theme index")
    return sections


def flat_index(sections):
    """Flatten sections into 'Section.key' -> value (deterministic order)."""
    flat = {}
    for section in sorted(sections):
        for key in sorted(sections[section]):
            flat[f"{section}.{key}"] = sections[section][key]
    return flat


def validate_index(sections):
    flat = flat_index(sections)
    name = next((v for k, v in flat.items() if k.endswith(".Name")), "")
    if not name:
        raise ThemeError("theme index has no Name")
    return name


def list_themes(root):
    """Scan a themes root for directories with a parsable index.theme."""
    if not os.path.isdir(root):
        raise ThemeError(f"no such themes root: {root!r}")
    out = []
    for entry in sorted(os.listdir(root)):
        index = os.path.join(root, entry, "index.theme")
        if not os.path.isfile(index):
            continue
        sections = parse_index(_read(index))
        name = validate_index(sections)
        flat = flat_index(sections)
        comment = next((v for k, v in flat.items()
                        if k.endswith(".Comment")), "")
        out.append({"dir": entry, "name": name, "comment": comment})
    return out


def parse_palette(text):
    """Parse `role = #hex` lines into a validated palette dict."""
    colors = {}
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(("#", ";", "//")):
            continue
        if "=" not in line:
            raise ThemeError(f"line {lineno}: expected 'role = #hex'")
        role, _, value = line.partition("=")
        role, value = role.strip().lower(), value.strip()
        if not _ROLE_RE.match(role):
            raise ThemeError(f"line {lineno}: bad role {role!r}")
        if not _HEX_RE.match(value):
            raise ThemeError(f"line {lineno}: bad color {value!r}")
        if role in colors and colors[role] != _norm_hex(value):
            raise ThemeError(f"line {lineno}: conflicting role {role!r}")
        colors[role] = _norm_hex(value)
    if not colors:
        raise ThemeError("palette is empty")
    return colors


def _rgb_delta(h1, h2):
    c1 = tuple(int(h1[i:i + 2], 16) for i in (1, 3, 5))
    c2 = tuple(int(h2[i:i + 2], 16) for i in (1, 3, 5))
    return int(round(math.dist(c1, c2)))


def diff_palettes(a, b):
    """Palette diff: added/removed/changed roles with RGB distance."""
    added = {k: b[k] for k in b if k not in a}
    removed = {k: a[k] for k in a if k not in b}
    changed = {}
    for k in sorted(a):
        if k in b and a[k] != b[k]:
            changed[k] = {"from": a[k], "to": b[k],
                          "delta": _rgb_delta(a[k], b[k])}
    return {"added": added, "removed": removed, "changed": changed}


def apply_plan(current, target, registry):
    """Ordered settings plan; unknown themes/settings fail fast."""
    unknown = [k for k in target if k not in _SETTING_ORDER]
    if unknown:
        raise ThemeError(f"unknown setting(s): {', '.join(sorted(unknown))} "
                         f"(allowed: {', '.join(_SETTING_ORDER)})")
    actions = []
    for key in _SETTING_ORDER:
        if key not in target:
            continue
        value = target[key]
        if key in _NAME_SETTINGS:
            if value not in registry:
                raise ThemeError(
                    f"unknown {key} {value!r} "
                    f"(installed: {', '.join(sorted(registry)) or 'none'})")
        elif key == "cursor-size":
            if isinstance(value, bool) or not isinstance(value, int) \
                    or not 1 <= value <= 256:
                raise ThemeError(f"cursor-size must be 1..256, got {value!r}")
        elif key == "font-size":
            if isinstance(value, bool) or not isinstance(value, int) \
                    or not 6 <= value <= 72:
                raise ThemeError(f"font-size must be 6..72, got {value!r}")
        elif key == "prefer-dark":
            if not isinstance(value, bool):
                raise ThemeError("prefer-dark must be true/false")
        elif not isinstance(value, str) or not value:
            raise ThemeError(f"{key} must be a non-empty string")
        if current.get(key) == value:
            continue  # no-op: never emit a redundant action
        rendered = str(value) if not isinstance(value, bool) else \
            ("true" if value else "false")
        if isinstance(value, str):
            rendered = f"'{value}'"
        actions.append({"set": key, "value": value,
                        "cmd": f"gsettings set {_SCHEMA[key]} {key} "
                               f"{rendered}"})
    return actions


def _sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _tree_hashes(root):
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for fname in sorted(filenames):
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, root)
            out[rel] = _sha(full)
    return out


def sync_plan(src, dst):
    """Plan syncing src into dst; never deletes anything silently."""
    if not os.path.isdir(src):
        raise ThemeError(f"no such source theme: {src!r}")
    src_files = _tree_hashes(src)
    dst_files = _tree_hashes(dst) if os.path.isdir(dst) else {}
    actions = []
    for rel in sorted(src_files):
        target = os.path.join(dst, rel)
        if os.path.isdir(target):
            raise ThemeError(f"conflict: {rel!r} exists as a directory")
        if rel not in dst_files:
            actions.append({"file": rel, "action": "copy", "reason": "new"})
        elif src_files[rel] != dst_files[rel]:
            actions.append({"file": rel, "action": "overwrite",
                            "reason": "content differs"})
        else:
            actions.append({"file": rel, "action": "skip",
                            "reason": "identical"})
    for rel in sorted(set(dst_files) - set(src_files)):
        actions.append({"file": rel, "action": "keep-extra",
                        "reason": "not in source (never delete silently)"})
    return actions


def cursor_plan(name, size, registry):
    """Cursor theme + size plan (GNOME/Cinnamon settings + legacy link)."""
    if name not in registry:
        raise ThemeError(f"unknown cursor theme {name!r} "
                         f"(installed: {', '.join(sorted(registry)) or 'none'})")
    if isinstance(size, bool) or not isinstance(size, int) \
            or not 1 <= size <= 256:
        raise ThemeError(f"cursor-size must be 1..256, got {size!r}")
    return {"theme": name, "size": size, "steps": [
        f"gsettings set org.gnome.desktop.interface cursor-theme '{name}'",
        f"gsettings set org.gnome.desktop.interface cursor-size {size}",
        f"ln -sfn ~/.icons/{name} ~/.icons/default  # legacy apps",
    ]}


def icons_plan(name, index_text, registry):
    """Validate an icon theme and its Inherits chain (cycles rejected)."""
    sections = parse_index(index_text)
    theme_name = validate_index(sections)
    flat = flat_index(sections)
    inherits_raw = next((v for k, v in flat.items()
                         if k.endswith(".Inherits")), "")
    inherits = [h.strip() for h in inherits_raw.split(",") if h.strip()]
    if theme_name == "hicolor" and not inherits:
        inherits = []
    if not inherits:
        raise ThemeError(f"icon theme {theme_name!r} inherits nothing")
    for parent in inherits:
        if parent == theme_name:
            raise ThemeError(f"icon theme inherits itself: {parent!r}")
        if parent not in registry and parent not in _BASE_INHERITS:
            raise ThemeError(
                f"icon theme inherits unknown theme {parent!r} "
                f"(available: {', '.join(sorted(registry)) or 'none'})")
    return {"name": theme_name, "inherits": inherits, "ok": True,
            "steps": [f"gsettings set org.gnome.desktop.interface "
                      f"icon-theme '{theme_name}'"]}


def diff_themes(a_root, b_root):
    """Diff two theme directories: index keys + palettes when present."""
    for label, root in (("a", a_root), ("b", b_root)):
        if not os.path.isfile(os.path.join(root, "index.theme")):
            raise ThemeError(f"theme {label} has no index.theme: {root!r}")
    fa = flat_index(parse_index(_read(os.path.join(a_root, "index.theme"))))
    fb = flat_index(parse_index(_read(os.path.join(b_root, "index.theme"))))
    index_diff = {k: {"a": fa[k], "b": fb[k]}
                  for k in sorted(set(fa) & set(fb)) if fa[k] != fb[k]}
    palette = None
    pa, pb = os.path.join(a_root, "palette.conf"), os.path.join(b_root, "palette.conf")
    if os.path.isfile(pa) and os.path.isfile(pb):
        palette = diff_palettes(parse_palette(_read(pa)),
                                parse_palette(_read(pb)))
    return {"index": index_diff,
            "only_a": sorted(set(fa) - set(fb)),
            "only_b": sorted(set(fb) - set(fa)),
            "palette": palette}


def _registry(root):
    return {t["name"] for t in list_themes(root)} | \
           {t["dir"] for t in list_themes(root)}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=ENGINE["name"],
                                description=ENGINE["summary"])
    sub = p.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="list installed themes")
    ls.add_argument("--root", required=True)
    ap = sub.add_parser("apply-plan", help="plan settings changes (dry run)")
    ap.add_argument("--root", required=True)
    ap.add_argument("--set", action="append", default=[], dest="sets",
                    metavar="KEY=VALUE")
    ap.add_argument("--current", default=None,
                    help="JSON file of current settings")
    sy = sub.add_parser("sync-plan", help="plan syncing a theme tree")
    sy.add_argument("src")
    sy.add_argument("dst")
    pa = sub.add_parser("palette", help="show a theme palette")
    pa.add_argument("theme_dir")
    pa.add_argument("--compare", default=None)
    cu = sub.add_parser("cursor", help="plan cursor theme + size")
    cu.add_argument("name")
    cu.add_argument("--root", required=True)
    cu.add_argument("--size", type=int, default=24)
    ic = sub.add_parser("icons", help="validate icon theme inheritance")
    ic.add_argument("name")
    ic.add_argument("--root", required=True)
    df = sub.add_parser("diff", help="diff two theme directories")
    df.add_argument("a")
    df.add_argument("b")
    return p


def _parse_sets(pairs):
    target = {}
    for pair in pairs:
        if "=" not in pair:
            raise ThemeError(f"--set needs KEY=VALUE, got {pair!r}")
        key, _, value = pair.partition("=")
        key = key.strip()
        if key in ("cursor-size", "font-size"):
            try:
                value = int(value)
            except ValueError as e:
                raise ThemeError(f"{key} must be an integer") from e
        elif key == "prefer-dark":
            if value not in ("true", "false"):
                raise ThemeError("prefer-dark must be true/false")
            value = value == "true"
        target[key] = value
    return target


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "list":
            themes = list_themes(args.root)
            if not themes:
                print(f"no themes found under {args.root}")
            for t in themes:
                print(f"{t['dir']:<20} {t['name']:<20} {t['comment']}")
        elif args.cmd == "apply-plan":
            current = {}
            if args.current:
                current = json.loads(_read(args.current))
            target = _parse_sets(args.sets)
            actions = apply_plan(current, target, _registry(args.root))
            if not actions:
                print("nothing to do (already applied)")
            for act in actions:
                print(act["cmd"])
        elif args.cmd == "sync-plan":
            actions = sync_plan(args.src, args.dst)
            counts = {}
            for act in actions:
                counts[act["action"]] = counts.get(act["action"], 0) + 1
                print(f"{act['action']:<10} {act['file']}  ({act['reason']})")
            print("summary: " + " ".join(f"{k}={v}" for k, v in
                                         sorted(counts.items())))
        elif args.cmd == "palette":
            colors = parse_palette(_read(os.path.join(args.theme_dir,
                                                      "palette.conf")))
            if args.compare:
                other = parse_palette(_read(os.path.join(args.compare,
                                                         "palette.conf")))
                diff = diff_palettes(colors, other)
                for role, info in diff["changed"].items():
                    print(f"changed {role}: {info['from']} -> {info['to']} "
                          f"(delta {info['delta']})")
                for role in sorted(diff["added"]):
                    print(f"added   {role}: {diff['added'][role]}")
                for role in sorted(diff["removed"]):
                    print(f"removed {role}: {diff['removed'][role]}")
                if not any(diff.values()):
                    print("palettes identical")
            else:
                for role in sorted(colors):
                    print(f"{role} = {colors[role]}")
        elif args.cmd == "cursor":
            plan = cursor_plan(args.name, args.size, _registry(args.root))
            for step in plan["steps"]:
                print(step)
        elif args.cmd == "icons":
            index_path = os.path.join(args.root, args.name, "index.theme")
            if not os.path.isfile(index_path):
                raise ThemeError(f"icon theme not found: {args.name!r}")
            plan = icons_plan(args.name, _read(index_path),
                              _registry(args.root))
            print(f"{plan['name']} inherits: "
                  f"{', '.join(plan['inherits']) or '(none)'}  [ok]")
            for step in plan["steps"]:
                print(step)
        elif args.cmd == "diff":
            result = diff_themes(args.a, args.b)
            for key, vals in result["index"].items():
                print(f"changed {key}: {vals['a']!r} -> {vals['b']!r}")
            for key in result["only_a"]:
                print(f"only in a: {key}")
            for key in result["only_b"]:
                print(f"only in b: {key}")
            if result["palette"]:
                pal = result["palette"]
                for role, info in pal["changed"].items():
                    print(f"palette {role}: {info['from']} -> {info['to']} "
                          f"(delta {info['delta']})")
                for role in sorted(pal["added"]):
                    print(f"palette added {role}: {pal['added'][role]}")
                for role in sorted(pal["removed"]):
                    print(f"palette removed {role}: {pal['removed'][role]}")
        return 0
    except (ThemeError, json.JSONDecodeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


def self_test() -> None:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        # --- theme directories ------------------------------------------------
        a = os.path.join(d, "Sigma-Dark")
        b = os.path.join(d, "Sigma-Light")
        os.makedirs(os.path.join(a, "assets"))
        os.makedirs(b)
        with open(os.path.join(a, "index.theme"), "w") as fh:
            fh.write("[X-GNOME-Metatheme]\n"
                     "Name=Sigma Dark\nComment=Dark variant\n"
                     "GtkTheme=Mint-Y-Dark\nIconTheme=Mint-Y\n"
                     "CursorTheme=Mint-Y\n")
        with open(os.path.join(b, "index.theme"), "w") as fh:
            fh.write("[X-GNOME-Metatheme]\n"
                     "Name=Sigma Light\nComment=Light variant\n"
                     "GtkTheme=Mint-Y\nIconTheme=Mint-Y\n")
        for root, body in ((a, "body {}\n"), (b, "body { color: #000; }\n")):
            with open(os.path.join(root, "gtk.css"), "w") as fh:
                fh.write(body)
        with open(os.path.join(a, "assets", "render.svg"), "w") as fh:
            fh.write("<svg/>\n")

        # --- index parsing / listing ------------------------------------------
        sections = parse_index(_read(os.path.join(a, "index.theme")))
        assert validate_index(sections) == "Sigma Dark"
        themes = list_themes(d)
        assert [t["dir"] for t in themes] == ["Sigma-Dark", "Sigma-Light"]
        assert themes[0]["comment"] == "Dark variant"

        # --- palette + palette diff -------------------------------------------
        pal_a = ("bg = #1e1e2e\nfg = #cdd6f4\naccent = #89b4fa\n"
                 "warn = #f9e2af\n")
        pal_b = ("bg = #181825\nfg = #cdd6f4\naccent = #cba6f7\n"
                 "muted = #6c7086\n")
        pa, pb = parse_palette(pal_a), parse_palette(pal_b)
        assert pa["bg"] == "#1e1e2e"
        diff = diff_palettes(pa, pb)
        assert set(diff["added"]) == {"muted"}
        assert set(diff["removed"]) == {"warn"}
        assert set(diff["changed"]) == {"bg", "accent"}
        assert diff["changed"]["bg"] == {"from": "#1e1e2e", "to": "#181825",
                                         "delta": 12}
        assert diff["changed"]["accent"]["delta"] > 60
        assert diff_palettes(pa, pa) == {"added": {}, "removed": {},
                                         "changed": {}}
        assert parse_palette("a = #abc\n")["a"] == "#aabbcc"  # short form
        for bad in ("no equals sign", "bg = #zzzzzz", "BG COLOR = #fff",
                    "bg = #fff\nbg = #000\n", "# only comments\n"):
            try:
                parse_palette(bad)
            except ThemeError:
                pass
            else:
                raise AssertionError(f"palette accepted: {bad!r}")

        # --- apply-plan --------------------------------------------------------
        registry = {"Mint-Y", "Mint-Y-Dark"}
        actions = apply_plan(
            {"gtk-theme": "Mint-Y-Dark", "cursor-size": 24},
            {"gtk-theme": "Mint-Y", "cursor-theme": "Mint-Y",
             "cursor-size": 32},
            registry)
        assert [act["set"] for act in actions] == \
            ["gtk-theme", "cursor-theme", "cursor-size"]
        assert actions[0]["cmd"] == \
            "gsettings set org.gnome.desktop.interface gtk-theme 'Mint-Y'"
        assert apply_plan({"cursor-size": 32}, {"cursor-size": 32},
                          registry) == []          # no-op suppressed
        for bad in (
            lambda: apply_plan({}, {"gtk-theme": "Nope"}, registry),
            lambda: apply_plan({}, {"cursor-size": 0}, registry),
            lambda: apply_plan({}, {"cursor-size": 9999}, registry),
            lambda: apply_plan({}, {"font-size": 3}, registry),
            lambda: apply_plan({}, {"prefer-dark": "yes"}, registry),
            lambda: apply_plan({}, {"bogus-key": 1}, registry),
        ):
            try:
                bad()
            except ThemeError:
                pass
            else:
                raise AssertionError("expected ThemeError")

        # --- sync-plan ---------------------------------------------------------
        os.makedirs(os.path.join(b, "assets"))
        with open(os.path.join(b, "assets", "render.svg"), "w") as fh:
            fh.write("<svg>new</svg>\n")           # differs from src version
        with open(os.path.join(a, "render.svg"), "w") as fh:
            fh.write("<svg>old</svg>\n")           # differ vs dst version
        with open(os.path.join(b, "extra.txt"), "w") as fh:
            fh.write("extra\n")                    # only in dst
        actions = sync_plan(a, b)
        by_file = {act["file"]: act["action"] for act in actions}
        assert by_file["gtk.css"] == "overwrite"
        assert by_file["assets/render.svg"] == "overwrite"
        assert by_file["extra.txt"] == "keep-extra"
        os.makedirs(os.path.join(b, "conflict"))
        with open(os.path.join(a, "conflict"), "w") as fh:
            fh.write("x\n")
        try:
            sync_plan(a, b)
        except ThemeError:
            pass
        else:
            raise AssertionError("directory/file conflict not caught")
        os.unlink(os.path.join(a, "conflict"))
        assert {act["action"] for act in sync_plan(a, a)} == {"skip"}

        # --- cursor + icons ----------------------------------------------------
        plan = cursor_plan("Mint-Y", 32, registry)
        assert any("cursor-size 32" in s for s in plan["steps"])
        for bad in (lambda: cursor_plan("Nope", 32, registry),
                    lambda: cursor_plan("Mint-Y", 0, registry)):
            try:
                bad()
            except ThemeError:
                pass
            else:
                raise AssertionError("expected ThemeError")
        icon_index = "[Icon Theme]\nName=Mint-Y-Dark\nInherits=Mint-Y,Adwaita\n"
        icons = icons_plan("Mint-Y-Dark", icon_index,
                           registry | {"Mint-Y-Dark"})
        assert icons["inherits"] == ["Mint-Y", "Adwaita"]
        for bad_index in ("[Icon Theme]\nName=X\n",          # no inherits
                          "[Icon Theme]\nName=X\nInherits=Ghost\n",
                          "[Icon Theme]\nName=X\nInherits=X\n"):
            try:
                icons_plan("X", bad_index, registry)
            except ThemeError:
                pass
            else:
                raise AssertionError("expected ThemeError")

        # --- diff --------------------------------------------------------------
        result = diff_themes(a, b)
        changed = {k: v for k, v in result["index"].items()}
        assert changed["X-GNOME-Metatheme.GtkTheme"] == \
            {"a": "Mint-Y-Dark", "b": "Mint-Y"}
        assert "X-GNOME-Metatheme.CursorTheme" in result["only_a"]
        with open(os.path.join(a, "palette.conf"), "w") as fh:
            fh.write(pal_a)
        with open(os.path.join(b, "palette.conf"), "w") as fh:
            fh.write(pal_b)
        result = diff_themes(a, b)
        assert result["palette"]["changed"]["bg"]["delta"] == 12

        # --- index validation --------------------------------------------------
        try:
            parse_index("[Bad\nName=x\n")
        except ThemeError:
            pass
        else:
            raise AssertionError("bad section accepted")
        try:
            parse_index("[S]\nName=a\nName=b\n")
        except ThemeError:
            pass
        else:
            raise AssertionError("duplicate key accepted")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
