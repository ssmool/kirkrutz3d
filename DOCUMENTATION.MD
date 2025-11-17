Below is a **complete, polished, professional module-by-module documentation set** for the **KIR KRUTZ 3D** project.
Each module includes:
✔ Overview
✔ Responsibilities
✔ Input / Output
✔ CLI usage
✔ Internal Workflow
✔ API functions
✔ Notes, limitations, and tips

Ready for direct placement into a `/docs/` folder or appended to README.

---

# 📘 **KIR KRUTZ 3D – Full Module Documentation**

# ================================================

# 1. MODULE: `analyzemap.py`

# ================================================

## 🔍 Overview

`analyzemap.py` is the **first stage** of the KIR KRUTZ 3D pipeline.
It reads an input bitmap (`.png/.jpg/.bmp`) and extracts:

* dominant colors
* color percentages
* per-color axis-line and spinline geometry (via LionsMapper AI)
* SVG graphical visualization
* metadata and human-readable reports

It prepares a **Blender-ready JSON** used later by the 3D generator.

---

## 🧠 Responsibilities

* Scan image pixels
* Identify unique colors
* Compute percentages
* Select top-N dominant colors
* For each color, run LionsMapper AI:

  * `_get_spin_route(image_path, (r, g, b))`
  * `_get_axis_line(0)`
* Produce JSON/CSV/SVG/TXT output
* Prepare datasets for `analyzemap_exporter` and `bitmap_3d.py`

---

## 📥 Inputs

* `map.png` (or any bitmap)

## 📤 Outputs

```
map.colors.json
map.colors.csv
map.svg
map.report.md
map.report.txt
```

---

## 🖥 CLI Usage

```
python analyzemap.py map.png --top 50 --threads 6 --csv --emit-blender
```

### Optional flags

| Flag                | Meaning                                 |
| ------------------- | --------------------------------------- |
| `--top N`           | use only the top N most frequent colors |
| `--threads N`       | parallel LionsMapper processing         |
| `--csv`             | generate CSV table                      |
| `--emit-blender`    | format JSON for Blender                 |
| `--out-prefix name` | use custom prefix                       |

---

## ⚙ Internal Workflow

1. Load image
2. Count RGB values
3. Select `top N` colors
4. For each color:

   * call LionsMapper AI to get axis lines
   * compute center, bounds, and route
5. Build JSON
6. Draw SVG visualization (legend + axis path)
7. Create TXT/MD report

---

## 🧩 API (importable)

```python
from KIR_KRUZT3D.analyzemap import analyze_image, save_json, save_svg
```

---

# ================================================

# 2. MODULE: `analyzemap_exporter.py`

# ================================================

## 📄 Overview

`analyzemap_exporter.py` converts raw analyzer results into external file formats:

* JSON
* CSV
* TXT (plain text report)
* SVG (vector visualization)

It acts as the “publication” layer of the pipeline.

---

## 🧠 Responsibilities

* Clean data exported from `analyzemap`
* Produce consistent metadata
* Ensure Blender compatibility
* Export diagnostic files

---

## 📥 Inputs

* internal data structure from `analyzemap`
* optionally loads `.json` to re-export

## 📤 Outputs

* `.json`, `.csv`, `.txt`, `.svg`

---

## 🖥 CLI Usage (if used standalone)

```
python analyzemap_exporter.py map.colors.json --csv --svg
```

---

## ⚙ Internal Workflow

1. Read metadata (colors, spinlines, axes)
2. Validate missing data gracefully
3. Normalize numeric data
4. Export to selected formats

---

## 🧩 API (importable)

```python
from KIR_KRUZT3D.analyzemap_exporter import (
    export_json,
    export_csv,
    export_svg,
    export_txt
)
```

---

# ================================================

# 3. MODULE: `bitmap_3d.py`

# ================================================

## 🧱 Overview

`bitmap_3d.py` is the **3D generator**, run **inside Blender**.
It converts the JSON output from `analyzemap` into:

* lithophanes
* mesh heightmaps
* color region extrusions
* solidified mesh objects
* previews
* combined GLB/OBJ/GLTF exports

This is the **geometry engine** of KIR KRUTZ 3D.

---

## 🖥 Blender Execution

```
blender --background --python bitmap_3d.py -- map.colors.json \
    --image-dir . --out-dir ./blender_out \
    --sample 4 --height-scale 0.02 \
    --rgb-tolerance 12 --solidify 0.5 \
    --export-format obj \
    --export-combined glb \
    --render-preview --preview-size 1024
```

---

## 🔧 Flags

| Flag                | Description                          |
| ------------------- | ------------------------------------ |
| `--image-dir PATH`  | locate original bitmap               |
| `--out-dir PATH`    | output folder                        |
| `--sample N`        | sampling resolution                  |
| `--height-scale`    | heightmap scaling (lithophane depth) |
| `--solidify`        | thickness                            |
| `--rgb-tolerance`   | color merging tolerance              |
| `--export-format`   | `obj`, `stl`, `ply`                  |
| `--export-combined` | merge results (`glb`, `gltf`, `obj`) |
| `--render-preview`  | render thumbnails                    |
| `--preview-size`    | resolution (px)                      |
| `--render-samples`  | cycles render samples                |

---

## 📥 Inputs

* `map.colors.json`
* Original image (optional, for heightmaps)

## 📤 Outputs

* Individual 3D models (`OBJ`, `STL`, etc.)
* Combined 3D model (GLB/GLTF/OBJ)
* Preview images
* Temporary metadata for `cam_sprites.py`

---

## ⚙ Internal Workflow

1. Load Blender
2. Import JSON parameters
3. Generate meshes per color
4. Apply height-scaling (lithophane)
5. Apply solidify modifier
6. Export meshes
7. Render previews (optional)
8. Build combined GLB file

---

## 🧩 API (importable)

```python
from KIR_KRUZT3D.bitmap_3d import generate_meshes, export_meshes
```

---

# ================================================

# 4. MODULE: `cam_sprites.py`

# ================================================

## 📸 Overview

`cam_sprites.py` is the **rendering & sprite generator**.
It takes existing 3D models and outputs:

* isometric renders
* orthographic renders
* multi-angle rotations (turntable)
* packed sprite sheets (PNG)

Perfect for game engines, UI icons, and asset packs.

---

## 🖥 Blender Execution Example

### **Combined GLB + previews**

```
blender --background --python cam_sprites.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out \
  --export-combined glb --render-preview \
  --preview-size 1024 --render-samples 64
```

### **Sprite Sheet**

```
blender --background --python cam_sprites.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out \
  --sprite-sheet --sprite-cols 4
```

---

## 🔧 Flags

| Flag               | Description                 |
| ------------------ | --------------------------- |
| `--sprite-sheet`   | generate final sprite sheet |
| `--sprite-cols N`  | number of columns           |
| `--render-ortho`   | orthographic camera         |
| `--render-preview` | preview PNG output          |
| `--render-samples` | cycles samples              |
| `--preview-size`   | render resolution           |

---

## 📥 Inputs

* 3D models exported from `bitmap_3d.py`
* Optional JSON for axis-based camera alignment

## 📤 Outputs

* Multi-angle PNG frames
* Combined sprite sheet PNG
* Optional GLB preview renders

---

## ⚙ Internal Workflow

1. Load 3D models
2. Setup camera rigs
3. Render turntable sequences
4. Generate spritesheet (via Pillow)

---

## 🧩 API (importable)

```python
from KIR_KRUZT3D.cam_sprites import render_sprites, build_spritesheet
```

---

# ================================================

# 5. MODULE: `upload_transfer_sh.py`

# ================================================

## 📤 Overview

Automates **uploading results** to transfer.sh for fast public sharing.
Used typically after generating:

* `combined.glb`
* sprite sheet (`spritesheet.png`)
* preview renders

---

## 🧠 Responsibilities

* Upload files to transfer.sh
* Provide public URLs
* Handle missing `requests` library gracefully
* Provide a single toggle: `--upload`

---

## 🖥 Blender Execution

```
blender --background --python upload_transfer.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out \
  --export-combined glb --render-preview \
  --sprite-sheet --sprite-cols 4 \
  --upload --upload-method transfer
```

---

## 🔧 Flags

| Flag                       | Description                  |
| -------------------------- | ---------------------------- |
| `--upload`                 | enable upload                |
| `--upload-method transfer` | default transfer.sh uploader |

---

## ⚙ Internal Workflow

1. Detect files to upload
2. Attempt uploading via `requests`
3. If unavailable, fall back to `urllib`
4. Print final URLs to Blender console

---

## 📤 Outputs

* Final URLs to combined assets
  Example:

```
https://transfer.sh/Hs8ks/combined_model.glb
https://transfer.sh/KLP92/spritesheet.png
```

---

## 🧩 API (importable)

```python
from KIR_KRUZT3D.upload_transfer_sh import upload_files
```

---

# ================================================

# 🧱 INSTALLER / PLUGIN: `dist/setup.exe`

# ================================================

## 🎩 Overview

A PyInstaller-based executable that:

* Installs KIR KRUTZ 3D as a **Blender Add-on**
* Provides a **wizard interface**
* Creates menus for quick-access commands

Supports Blender automation without command-line usage.

---

## Features

* Windows installer
* Auto-detects Blender directory
* Copies scripts to add-ons folder
* Registers new “KIR KRUTZ 3D Tools” panel
* Includes About/Credits page

---

# ================================================

# 💬 Closing Notes

Each module is designed to be:

* **standalone**
* **chainable**
* **importable**
* **Blender-friendly**
* **AI-optimized**

The **KIR KRUTZ 3D pipeline** turns any image into:

1. structured data
2. 3D geometry
3. preview renders
4. spritesheets
5. uploadable assets

All with automation, AI-processing, and Blender synergy.
