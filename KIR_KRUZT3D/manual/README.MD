MANUAL:

ANALIZE MAP [analyzemap.py]:

from analizemap import *

USAGE:
python analyzemap.py map.png --top 50 --threads 6 --csv --emit-blender
map.colors.json (with per-color params auto-set)
map.colors.csv
map.svg
map.report.md / map.report.txt

CLI:image_to_3d_blender_lithophane.py
CLI(BLENDER):blender --background --python image_to_3d_blender_lithophane.py -- map.colors.json --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.6 --export-format obj

"""
analyzemap.py

Usage examples:
    python analyzemap.py map.png
    python analyzemap.py map.png --top 20 --threads 8 --out-prefix mymap

Features:
 - Extracts RGB colors and their percentages (optionally limit top N)
 - Uses multithreading to call lionsmapper functions for each color:
     _get_spin_route(image_path, (r,g,b))
     _get_axis_line(0)
 - Saves JSON with percentages and axis coordinates
 - Creates an SVG with embedded image, color legend, and drawn axis coords
 - Produces a Markdown and TXT human-readable report
"""

-----

Analyzemap Exporter [analyzemap_exporter.py]:

# IMPORTANT: lionsmapper functions are used as requested.
# The user said they have: from lionsmapper import *
# We will import here; if lionsmapper isn't available the script will still run but skip processing.

-----

BITMAP 3D [bitmap_3d.py]

# replace:image_to_3d_blender_lithophane.py
# bitmap_3d.py
# Run inside Blender:
# blender --background --python image_to_3d_blender_lithophane.py -- results.colors.json --image-dir . --out-dir ./blender_out \
#    --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.5 --export-format obj \
#    --export-combined glb --render-preview --preview-size 1024
#
# Flags:
# --export-combined [glb|gltf|obj]    => export ALL generated meshes into ONE combined file (glb recommended)
# --render-preview                     => render PNG thumbnails (one combined + one per color)
# --preview-size N                     => square size in px (default 1024)
# --render-samples N                   => render samples (default 32)
# --preview-dpi                         => (optional) not used here, reserved

-----

Cam Sprites.py [cam_sprites.py]

cli:1.Produce combined GLB + previews for map.colors.json:
blender --background --python bitmap_3d.py -- map.colors.json --image-dir . --out-dir ./blender_out \
  --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.6 --export-format obj \
  --export-combined glb --render-preview --preview-size 1024 --render-samples 64"""

cli:2.Only combined export (no individual exports, no previews):
blender --background --python bitmap_3d.py -- map.colors.json --image-dir . --out-dir ./blender_out \
  --export-combined glb"""

cli:blender --background --python bitmap_3d_final.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 \
  --solidify 0.6 --export-format obj --export-combined glb --render-preview --render-ortho \
  --preview-size 1024 --render-samples 64 --sprite-sheet --sprite-cols 4"""

#Only combined export, no renders:

cli:blender --background --python bitmap_3d_final.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out --export-combined glb --no-preview
  
Upload Transfer sh [upload_transfer_sh.py]

Perfect — below is the final Blender lithophane script with automatic transfer.sh upload integrated (transfer.sh is the default method, per your choice). After the script finishes exporting the combined GLB and sprite-sheet PNG, it will attempt to upload them to transfer.sh and print the returned public URLs in Blender’s console.

Notes:

    The script tries to use requests for upload (faster & cleaner). If requests is not available in Blender’s Python, it falls back to urllib (which should work in modern Blender Python builds).

    If you prefer S3 or Gist later, the uploader function can be extended — but transfer.sh is implemented now as requested.

    Save this as upload_transfer.py and run inside Blender the same way as previous examples. The new flags are --upload (default on) and --upload-method (defaults to transfer).


# upload_transfer.py
# Final Blender script with automatic upload to transfer.sh (default).
#
# Usage (example):
# blender --background --python upload_transfer.py -- map.colors.json \
#   --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 \
#   --solidify 0.6 --export-format obj --export-combined glb --render-preview --render-ortho \
#   --preview-size 1024 --render-samples 64 --sprite-sheet --sprite-cols 4 --upload --upload-method transfer
#
# The script will:
#  - generate per-color lithophane meshes (as before)
#  - export per-object files (obj/stl), optionally a combined GLB
#  - render perspective and orthographic previews
#  - compose a sprite sheet (if Pillow installed)
#  - upload combined + sprite_sheet to transfer.sh (by default) and print resulting URLs
