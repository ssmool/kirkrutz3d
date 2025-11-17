#!/usr/bin/env python3
"""
KIR_KRUTZ3D Add-on Installer bootstrap
This small script copies the included add-on files (bundled alongside this binary)
into the user's Blender add-ons directory.
"""
import os
import sys
import shutil
import zipfile
from pathlib import Path

ADDON_NAME = "KIR_KRUTZ3D_addon"
# Default Blender user addons location pattern (adjustable)
# We will attempt to detect Blender user folder by scanning common locations.

def guess_blender_user_addons():
    home = Path.home()
    possible = []
    # common Linux/Mac path
    for ver in range(3, 4):
        # we can't know exact minor version; allow searching
        globpath = home / f".config/blender"
        if globpath.exists():
            for version_dir in globpath.iterdir():
                addons = version_dir / "scripts" / "addons"
                if addons.exists():
                    possible.append(addons)
    # Windows user path (AppData)
    appdata = os.environ.get('APPDATA')
    if appdata:
        base = Path(appdata) / "Blender Foundation"
        if base.exists():
            for version_dir in base.iterdir():
                addons = version_dir / "scripts" / "addons"
                if addons.exists():
                    possible.append(addons)
    # fallback: return home + ".blender_addons"
    possible.append(home / ".blender_addons")
    return possible


def extract_and_install(target_addons_path):
    cwd = Path(__file__).parent
    # If this executable is a onefile PyInstaller, bundled files are extracted
    # next to the executable in a temporary folder; we try to locate KIR_KRUZT3D_addon.py
    # within cwd or within a subfolder 'KIR_KRUZT3D_addon'.
    found = []
    for p in [cwd, cwd / 'KIR_KRUZT3D_addon', cwd / 'data']:
        candidate = p / 'KIR_KRUZT3D_addon.py'
        if candidate.exists():
            found.append(candidate)
    if not found:
        print('ERROR: bundled add-on file not found. Make sure KIR_KRUZT3D_addon.py is bundled.')
        return False
    # ensure target dir exists
    target = Path(target_addons_path)
    target.mkdir(parents=True, exist_ok=True)
    # copy files
    for src in found:
        dst = target / src.name
        shutil.copy2(src, dst)
        print(f'Copied {src} -> {dst}')
    # copy resource folder if included
    res = cwd / 'resources'
    if res.exists() and res.is_dir():
        destres = target / 'resources'
        if destres.exists():
            shutil.rmtree(destres)
        shutil.copytree(res, destres)
        print(f'Copied resources -> {destres}')
    print('Installation complete. Please enable the add-on in Blender Preferences > Add-ons.')
    return True

if __name__ == '__main__':
    cand = guess_blender_user_addons()
    print('Detected potential Blender addons paths:')
    for idx, p in enumerate(cand):
        print(f'  {idx+1}. {p}')
    print('Choose a target path number to install, or enter a custom path:')
    try:
        choice = input('Target [1]: ').strip()
    except Exception:
        choice = '1'
    if not choice:
        choice = '1'
    try:
        choice_idx = int(choice)-1
        target = cand[choice_idx]
    except Exception:
        target = Path(choice)
    ok = extract_and_install(target)
    if not ok:
        sys.exit(2)
    sys.exit(0)
