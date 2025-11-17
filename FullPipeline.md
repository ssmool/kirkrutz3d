# 🎛️ **1. Full Pipeline**

## **ASCII Version (for README.md)**

```
 ┌─────────────────────────────────────────────┐
 │                INPUT IMAGE                  │
 │                 map.png                     │
 └──────────────────────────┬──────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────┐
 │          1. analyzemap.py (AI)             │
 │---------------------------------------------│
 │ - Extract dominant RGB colors               │
 │ - Compute percentages                       │
 │ - Call LionsMapper AI:                      │
 │     _get_spin_route(), _get_axis_line()     │
 │ - Generate: JSON, CSV, SVG, MD, TXT         │
 └──────────────────────────┬──────────────────┘
                            │
                 produces   │ map.colors.json
                            │
                            ▼
 ┌─────────────────────────────────────────────┐
 │         2. analyzemap_exporter.py           │
 │---------------------------------------------│
 │ - Clean & validate analyzer data            │
 │ - Export JSON/CSV/SVG/TXT                   │
 │ - Prepare Blender-ready metadata            │
 └──────────────────────────┬──────────────────┘
                            │
                            ▼
 ┌─────────────────────────────────────────────┐
 │     3. bitmap_3d.py (Blender Geometry)     │
 │---------------------------------------------│
 │ - Generate 3D meshes per color              │
 │ - Lithophane heightmaps                     │
 │ - Solidify geometry                         │
 │ - Export OBJ/STL/PLY                        │
 │ - Combine into GLB/GLTF/OBJ                 │
 │ - Render previews                           │
 └──────────────────────────┬──────────────────┘
                            │
                            │  exports
                            ▼
 ┌─────────────────────────────────────────────┐
 │         4. cam_sprites.py (Renders)         │
 │---------------------------------------------│
 │ - Multi-angle preview renders               │
 │ - Orthographic / perspective                │
 │ - Turntable frames                          │
 │ - Compose sprite sheets (PNG)               │
 └──────────────────────────┬──────────────────┘
                            │
                            │  produces
                            ▼
 ┌─────────────────────────────────────────────┐
 │   5. upload_transfer_sh.py (Publishing)     │
 │---------------------------------------------│
 │ - Upload combined GLB + spritesheet         │
 │ - Uses transfer.sh                          │
 │ - Prints public download URLs               │
 └──────────────────────────┘
```

---

## **Mermaid Flowchart Version (for Docs Site)**

```mermaid
flowchart TD

A[Input Bitmap Image<br>map.png] --> B[1. analyzemap.py<br><b>Color extraction + AI spinlines</b><br>Outputs: JSON, CSV, SVG, MD]

B --> C[2. analyzemap_exporter.py<br><b>Formatting + Normalization</b><br>Outputs: Cleaned metadata]

C --> D[3. bitmap_3d.py (Blender)<br><b>3D Mesh Generator</b><br>Outputs: OBJ/STL/PLY + GLB + previews]

D --> E[4. cam_sprites.py<br><b>Render Frames + Sprite Sheets</b><br>Outputs: PNG previews + spritesheets]

E --> F[5. upload_transfer_sh.py<br><b>Auto Upload</b><br>Outputs: Public URLs via transfer.sh]
```

---

# 🌐 **2. FULL API REFERENCE SITE**

Below is a **complete API documentation** for publishing as a docs website.
This structure is compatible with:

### ✔ MkDocs

### ✔ MkDocs Material

### ✔ Sphinx

### ✔ GitHub Pages

### ✔ ReadTheDocs

Copy this into `/docs/api/` for a working reference.

---

# =========================================

# 📚 KIR KRUTZ 3D – API REFERENCE SITE

# =========================================

# 🏠 Overview

KIR KRUTZ 3D is a Python + Blender + AI pipeline that converts images into:

* color maps
* spinlines and axes
* 3D meshes
* GLB/OBJ exports
* sprite sheets
* rendered previews
* online-hosted public files

This documentation covers all importable Python APIs.

---

# =========================================

# 📘 API: analyzemap.py

# =========================================

## Module Summary

Extracts RGB color frequencies, computes percentages, detects regions, and uses LionsMapper AI to compute geometric descriptors.

---

## Functions

### ### `analyze_image(image_path, top_n=0, threads=4)`

**Description:**
Analyzes bitmap colors and optionally limits to top N colors.

**Parameters:**

| Name         | Type | Description                     |
| ------------ | ---- | ------------------------------- |
| `image_path` | str  | Path to bitmap                  |
| `top_n`      | int  | Limit dominant colors (0 = all) |
| `threads`    | int  | Thread count for AI calls       |

**Returns:**
`dict` – structured color analysis result.

---

### `extract_color_stats(image)`

Extract raw pixel frequencies.

Returns RGB count table.

---

### `run_lionsmapper_for_color(image_path, rgb_tuple)`

Runs:

* `_get_spin_route(image_path, (r,g,b))`
* `_get_axis_line(0)`

Returns AI-generated geometry.

---

### `save_json(data, path)`

Writes JSON with UTF-8 formatting.

---

### `create_svg_visualization(image_path, analysis, out_path)`

Draws:

* embedded raster
* axis lines
* color legend

---

### `write_text_report(data, path_md, path_txt)`

Generates MD/TXT documentation.

---

# =========================================

# 📘 API: analyzemap_exporter.py

# =========================================

## Module Summary

Exports analyzer results to external file formats.

---

## Functions

### `export_json(data, path)`

Writes JSON file.

---https://github.com/ssmool

### `export_csv(data, path)`

Exports color frequencies and coordinates.

---

### `export_txt(data, path)`

Plain-text summarization.

---

### `export_svg(image_path, data, path)`

Rebuilds visualization.

---

### `load_analysis(path)`

Loads `.colors.json`.

---

# =========================================

# 📘 API: bitmap_3d.py

# =========================================

## Module Summary

Runs inside Blender. Generates heightmap meshes, solidified models, and combined exports.

---

## Functions

### `load_analysis_json(path)`

Parse Blender-ready JSON from `analyzemap.py`.

---

### `generate_meshes(analysis, image_dir, settings)`

Creates mesh objects in Blender.

`settings` may include:

* `sample`
* `height_scale`
* `solidify`
* `rgb_tolerance`

---

### `apply_solidify(obj, thickness)`

Applies solidify modifier.

---

### `export_meshes(objs, out_dir, fmt)`

Exports OBJ/STL/PLY.

---

### `export_combined_scene(out_dir, fmt)`

Exports a single combined GLB/GLTF/OBJ.

---

### `render_preview(obj, out_dir, size, samples)`

Renders single preview PNG.

---

### `render_all_previews(objs, out_dir, settings)`

Batch preview rendering.

---

# =========================================

# 📘 API: cam_sprites.py

# =========================================

## Module Summary

Renders multi-angle camera views and builds sprite sheets.

---

## Functions

### `setup_cameras(mode="ortho")`

Creates cameras for orthographic or perspective rendering.

---

### `render_turntable(obj, angles, out_dir, settings)`

Renders multiple rotations.

---

### `compose_spritesheet(images, output_path, cols)`

Builds a final PNG using Pillow.

---

### `render_sprites(analysis, meshes, out_dir, settings)`

One-shot sprite generation.

---

# =========================================

# 📘 API: upload_transfer_sh.py

# =========================================

## Module Summary

Uploads generated files to transfer.sh.

---

## Functions

### `upload_file_transfer_sh(file_path)`

Uploads file; returns public URL.

Fallbacks to urllib if requests unavailable.

---

### `upload_files(file_list)`

Batch upload; returns dict `{filename: url}`.

---

### `upload_from_blender(output_dir, upload=True)`

Used by Blender final scripts.

---

# =========================================

# 📘 Additional Pages for the Docs Site

# =========================================

## 🛠 Configuration

Explains global settings, environment variables, Blender paths.

## 📦 Installation

Explains:

* Python setup
* Blender add-on install
* Using `dist/setup.exe` installer

## 🧪 Examples

Contains ready-to-run pipelines:

### Example: Full Pipeline

```
python analyzemap.py map.png
blender --background --python bitmap_3d.py -- map.colors.json ...
blender --background --python cam_sprites.py -- map.colors.json ...
blender --background --python upload_transfer.py -- map.colors.json ...
```

## ❓ FAQ

* Memory usage
* Why previews render black
* Why GLB is large
* LionsMapper AI installation
* Blender scripting tips

---

# 🎉 All Documentation Delivered!

You now have:

✔ Complete pipeline flowchart (ASCII + Mermaid)
✔ Full API reference formatted for a standalone docs site
✔ Fully structured module-by-module breakdown
