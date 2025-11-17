#cli: python analyzemap.py map.png --top 50 --threads 6 --csv --emit-blender
#cli:mage_to_3d_blender_lithophane.py
#cli:blender --background --python image_to_3d_blender_lithophane.py -- map.colors.json --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --#rgb-tolerance 12 --solidify 0.6 --export-format obj

"""Features:
 - Extracts RGB colors and percentages (optionally top N)
 - Multithreaded caimage_to_3d_blender_lithophane.plls to lionsmapper (if available)
 - Saves JSON, CSV, Markdown/TXT report, and SVG with overlays
 - Auto-injects per-color parameters into JSON (so Blender script can use per-color overrides)
 - Emits Blender lithophane generator script: image_to_3d_blender_lithophane.py
map.colors.json (with per-color params auto-set)
map.colors.csv
map.svg
map.report.md / map.report.txt
"""

import argparse
import base64
import io
import json
import math
import os
import sys
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from PIL import Image
import svgwrite

# Try import lionsmapper
try:
    from lionsmapper import _get_spin_route, _get_axis_line
    LIONS_AVAILABLE = True
except Exception:
    LIONS_AVAILABLE = False
    def _get_spin_route(image, rgb): raise RuntimeError("lionsmapper missing")
    def _get_axis_line(x): raise RuntimeError("lionsmapper missing")

# ---------- Utilities ----------
def normalize_axis_coords(axis_data):
    if axis_data is None:
        return []
    if isinstance(axis_data, str):
        try:
            parsed = json.loads(axis_data)
            return normalize_axis_coords(parsed)
        except Exception:
            return []
    if isinstance(axis_data, (list, tuple)):
        out = []
        for item in axis_data:
            if item is None:
                continue
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                try:
                    x = float(item[0]); y = float(item[1]); out.append((x,y)); continue
                except Exception:
                    pass
            if isinstance(item, dict):
                if "x" in item and "y" in item:
                    try:
                        out.append((float(item["x"]), float(item["y"]))); continue
                    except Exception: pass
                # fallback: look at values
                vals = list(item.values())
                nested = normalize_axis_coords(vals)
                if nested:
                    out.extend(nested); continue
            nested2 = normalize_axis_coords(item)
            if nested2:
                out.extend(nested2)
        return out
    if isinstance(axis_data, dict):
        out = []
        for v in axis_data.values():
            out.extend(normalize_axis_coords(v))
        return out
    try:
        if hasattr(axis_data, "__len__") and len(axis_data) >= 2:
            return [(float(axis_data[0]), float(axis_data[1]))]
    except Exception:
        pass
    return []

def embed_image_datauri(path):
    ext = os.path.splitext(path)[1].lower().lstrip('.')
    if ext == 'jpg': ext = 'jpeg'
    with open(path, "rb") as f:
        b = f.read()
    return f"data:image/{ext};base64," + base64.b64encode(b).decode('ascii')

def human_pct(p): return f"{p:.4f}%"

# ---------- Color analysis ----------
def analyze_colors(image_path, top_n=None):
    img = Image.open(image_path).convert("RGB")
    pixels = list(img.getdata())
    total = len(pixels)
    counts = Counter(pixels)
    items = [(rgb, cnt, (cnt/total)*100.0) for rgb,cnt in counts.items()]
    items.sort(key=lambda x: x[2], reverse=True)
    if top_n and top_n>0:
        items = items[:top_n]
    return items, img.size

# ---------- LionsMapper processing ----------
def process_color_task(image_path, rgb):
    res = {"color": rgb, "error": None, "axis_raw": None, "axis_coords": []}
    try:
        if not LIONS_AVAILABLE:
            raise RuntimeError("lionsmapper not available")
        _get_spin_route(image_path, tuple(rgb))
        raw = _get_axis_line(0)
        res["axis_raw"] = raw
        res["axis_coords"] = normalize_axis_coords(raw)
    except Exception as e:
        res["error"] = str(e)
    return res

def run_threaded(image_path, color_entries, workers=4):
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {}
        for rgb,count,pct in color_entries:
            fut = ex.submit(process_color_task, image_path, rgb)
            futures[fut] = (rgb,count,pct)
        for fut in as_completed(futures):
            rgb,count,pct = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                r = {"color": rgb, "error": f"worker failure: {e}", "axis_coords": []}
            out[str(rgb)] = {"rgb": list(rgb), "count": count, "percentage": pct, "processing": r}
    return out

# ---------- Auto per-color param injection ----------
def auto_inject_params(results_dict, base_height=0.02, base_solidify=0.5, base_sample=4):
    """
    Inject 'params' dict for each color entry based on prevalence.
    Rules (example):
     - More prevalent colors => slightly larger height_scale and thicker solidify
     - height_scale = base_height * (1 + pct/100 * 0.5)
     - solidify = base_solidify * (1 + pct/100 * 0.5)
     - sample: higher prevalence -> use slightly lower sample (more detail)
    """
    for key, entry in results_dict.items():
        pct = entry.get("percentage", 0.0)
        height_scale = base_height * (1.0 + (pct/100.0)*0.6)   # tuneable
        solidify = base_solidify * (1.0 + (pct/100.0)*0.5)
        # map pct to sample: high pct => sample down to 2; low pct => up to base_sample*2
        sample = max(2, int(round(base_sample * (1.0 + (50 - min(pct,50))/50.0))))
        # choose export fmt default obj
        params = {
            "height_scale": round(height_scale, 6),
            "solidify": round(solidify, 6),
            "sample": sample,
            "export_format": "obj",
            "material_name": f"mat_{entry['rgb'][0]}_{entry['rgb'][1]}_{entry['rgb'][2]}"
        }
        entry["params"] = params
    return results_dict

# ---------- Output writers ----------
def save_json(wrapper, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wrapper, f, indent=2, ensure_ascii=False)

def save_csv(results, path):
    with open(path, "w", newline='', encoding="utf-8") as csvf:
        writer = csv.writer(csvf)
        writer.writerow(["rgb", "count", "percentage", "axis_count", "axis_coords_json", "processing_error"])
        for k,v in results.items():
            rgb = tuple(v["rgb"])
            cnt = v["count"]
            pct = v["percentage"]
            proc = v.get("processing", {})
            axis = proc.get("axis_coords", []) if isinstance(proc, dict) else []
            err = proc.get("error") if isinstance(proc, dict) else None
            writer.writerow([str(rgb), cnt, f"{pct:.6f}", len(axis), json.dumps(axis, ensure_ascii=False), err or ""])

def save_reports(results, md_path, txt_path, image_name, image_size):
    now = datetime.utcnow().isoformat() + "Z"
    md_lines = [f"# Report for `{image_name}`\n\n- Generated: {now}\n- Image size: {image_size[0]}x{image_size[1]} px\n\n"]
    txt_lines = [f"Report for {image_name}\nGenerated: {now}\nImage size: {image_size[0]}x{image_size[1]} px\n\n"]
    md_lines.append("## Colors (sorted)\n")
    for k,v in results.items():
        rgb = v["rgb"]; pct = v["percentage"]; cnt = v["count"]
        md_lines.append(f"### `{tuple(rgb)}` — {human_pct(pct)} ({cnt} px)\n")
        txt_lines.append(f"{tuple(rgb)} — {human_pct(pct)} ({cnt} px)\n")
        proc = v.get("processing", {})
        err = proc.get("error") if isinstance(proc, dict) else None
        axis = proc.get("axis_coords", []) if isinstance(proc, dict) else []
        if err:
            md_lines.append(f"- Processing error: `{err}`\n\n")
            txt_lines.append(f"  Processing error: {err}\n\n")
        else:
            md_lines.append(f"- Axis coords count: {len(axis)}\n\n")
            txt_lines.append(f"  Axis coords count: {len(axis)}\n\n")
    with open(md_path, "w", encoding="utf-8") as f: f.writelines(md_lines)
    with open(txt_path, "w", encoding="utf-8") as f: f.writelines(txt_lines)

def create_svg(image_path, results, image_size, out_svg, embed=True):
    w,h = image_size
    legend_w = 320; pad = 12
    svg_w = w + legend_w + pad*3
    svg_h = max(h, 300) + pad*2
    dwg = svgwrite.Drawing(out_svg, size=(svg_w, svg_h), profile='full')
    dwg.add(dwg.rect(insert=(0,0), size=(svg_w, svg_h), fill='white'))
    if embed:
        try:
            datauri = embed_image_datauri(image_path)
            dwg.add(dwg.image(href=datauri, insert=(pad,pad), size=(w,h)))
        except Exception as e:
            print("Warning: embed failed:", e)
    legend_x = pad*2 + w; legend_y = pad
    dwg.add(dwg.text("Legend & overlays", insert=(legend_x, legend_y+14), font_size=14, font_weight='bold'))
    y = legend_y + 36; entry_h = 30
    for key, info in results.items():
        rgb = info["rgb"]; pct = info["percentage"]; proc = info.get("processing", {})
        hexc = '#%02x%02x%02x' % tuple(rgb)
        dwg.add(dwg.rect(insert=(legend_x, y), size=(18,18), fill=hexc, stroke='black', stroke_width=0.5))
        label = f"{tuple(rgb)} — {human_pct(pct)}"
        if isinstance(proc, dict) and proc.get("error"):
            label += " (err)"
        dwg.add(dwg.text(label, insert=(legend_x+26, y+14), font_size=12))
        # plot axis coords if any
        axis = proc.get("axis_coords", []) if isinstance(proc, dict) else []
        for i,pt in enumerate(axis):
            try:
                x,y_pt = pt; cx = pad + max(0,min(w,x)); cy = pad + max(0,min(h,y_pt))
                dwg.add(dwg.circle(center=(cx,cy), r=3, fill=hexc, stroke='black', stroke_width=0.4))
            except Exception:
                continue
        y += entry_h
        if y > svg_h - 40: break
    dwg.add(dwg.text(f"Generated: {datetime.utcnow().isoformat()}Z", insert=(12, svg_h-8), font_size=8, fill='gray'))
    dwg.save()

# ---------- Blender KIR_KRUTZ3D emitter (writes the final script file) ----------
BLENDER_KRIRKRUTZ3D_SCRIPT = r'''# bitmap_3d.py
# Auto-generated KRIRKRUTZ3D generator. Run inside Blender:
# blender --background --python bitmap_3d.py -- results.colors.json --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.5 --export-format obj

import bpy, os, sys, json, math
from mathutils import Vector

def parse_argv():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--")+1:]
    else:
        argv = []
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("results_json")
    p.add_argument("--image-dir", default=".")
    p.add_argument("--out-dir", default="./blender_out")
    p.add_argument("--sample", type=int, default=4)
    p.add_argument("--height-scale", type=float, default=0.02)
    p.add_argument("--rgb-tolerance", type=float, default=12.0)
    p.add_argument("--solidify", type=float, default=0.5)
    p.add_argument("--export-format", default="obj", choices=["obj","stl"])
    p.add_argument("--max-colors", type=int, default=0)
    return p.parse_args(argv)

def ensure_dir(d): os.makedirs(d, exist_ok=True)

def load_image_bpy(path):
    try:
        img = bpy.data.images.load(path)
        if not img.has_data:
            img.pixels[:]
        return img
    except Exception as e:
        print("ERROR loading image:", e); return None

def color_dist(a,b):
    return math.sqrt((a[0]-b[0])**2 + (a[1]-b[1])**2 + (a[2]-b[2])**2)

def brightness(rgb):
    r,g,b = rgb
    return (0.2126*r + 0.7152*g + 0.0722*b)/255.0

def img_pixel(img, x, y):
    w,h = img.size[0], img.size[1]
    if x<0: x=0
    if x>=w: x=w-1
    if y<0: y=0
    if y>=h: y=h-1
    idx = (y*w + x)*4
    px = img.pixels[idx:idx+4]
    r = int(px[0]*255+0.5); g = int(px[1]*255+0.5); b = int(px[2]*255+0.5); a = px[3]
    return (r,g,b,a)

def create_material(rgb, name=None):
    rn,gn,bn = [c/255.0 for c in rgb]
    name = name or f"mat_{rgb[0]}_{rgb[1]}_{rgb[2]}"
    mat = bpy.data.materials.get(name)
    if mat: return mat
    mat = bpy.data.materials.new(name); mat.use_nodes=True
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    nodes.clear()
    out = nodes.new(type='ShaderNodeOutputMaterial'); bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (rn,gn,bn,1); bsdf.inputs['Roughness'].default_value = 0.6
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat

def build_grid_mesh(name, grid, wpts, hpts, pxscale):
    verts=[]; faces=[]
    for j in range(hpts):
        for i in range(wpts):
            x = i*pxscale; y = j*pxscale; z = grid[j][i]
            verts.append((x,y,z))
    for j in range(hpts-1):
        for i in range(wpts-1):
            a = j*wpts + i; b=a+1; c=a+wpts+1; d=a+wpts
            faces.append((a,b,c,d))
    mesh = bpy.data.meshes.new(name+"_mesh"); mesh.from_pydata(verts,[],faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh); bpy.context.collection.objects.link(obj)
    return obj

def main():
    args = parse_argv()
    ensure_dir(args.out_dir)
    with open(args.results_json,'r',encoding='utf-8') as f: data=json.load(f)
    image_name = data.get("image")
    if not image_name:
        print("JSON missing 'image'"); return
    img_path = os.path.join(args.image_dir, image_name)
    if not os.path.exists(img_path):
        print("Image not found:", img_path); return
    img = load_image_bpy(img_path); w,h = img.size[0], img.size[1]
    items = list(data.get("colors", {}).items())
    if args.max_colors>0: items = items[:args.max_colors]
    for key,info in items:
        rgb = info.get("rgb",[255,255,255]); rgb = [int(x) for x in rgb]
        params = info.get("params",{}) or {}
        sample = int(params.get("sample", args.sample))
        height_scale = float(params.get("height_scale", args.height_scale))
        solidify = float(params.get("solidify", args.solidify))
        export_fmt = params.get("export_format", args.export_format)
        mat_name = params.get("material_name", None)
        print("Processing", rgb, "sample", sample, "hscale", height_scale)
        wpts = max(2, w//sample); hpts = max(2, h//sample)
        grid = [[0.0 for _ in range(wpts)] for __ in range(hpts)]
        anymask=False
        for j in range(hpts):
            for i in range(wpts):
                px = min(w-1, i*sample); py = min(h-1, j*sample)
                pr,pg,pb,pa = img_pixel(img, px, py)
                if color_dist((pr,pg,pb), tuple(rgb)) <= args.rgb_tolerance:
                    br = brightness((pr,pg,pb)); hh = (1.0 - br) * height_scale; grid[j][i] = hh; anymask=True
                else:
                    grid[j][i] = 0.0
        if not anymask:
            print("skip color", rgb, "no masked pixels"); continue
        name = f"color_{rgb[0]}_{rgb[1]}_{rgb[2]}"
        obj = build_grid_mesh(name, grid, wpts, hpts, sample)
        bpy.context.view_layer.update()
        bbox=[Vector(b) for b in obj.bound_box]
        minx=min(v.x for v in bbox); maxx=max(v.x for v in bbox); miny=min(v.y for v in bbox); maxy=max(v.y for v in bbox)
        centerx = (minx+maxx)/2.0; centery=(miny+maxy)/2.0
        obj.location = (-centerx, -centery, 0.0)
        mat = create_material(rgb, name=mat_name)
        if obj.data.materials: obj.data.materials[0]=mat
        else: obj.data.materials.append(mat)
        mod = obj.modifiers.new(name="Solidify", type='SOLIDIFY'); mod.thickness = solidify; mod.offset=1.0
        for f in obj.data.polygons: f.use_smooth=True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        outfile = os.path.join(args.out_dir, name + "." + export_fmt)
        bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active = obj
        if export_fmt == "obj": bpy.ops.export_scene.obj(filepath=outfile, use_selection=True, use_materials=True)
        elif export_fmt == "stl": bpy.ops.export_mesh.stl(filepath=outfile, use_selection=True)
        print("Exported", outfile)

if __name__ == "__main__": main()
'''

def emit_blender_script(path="bitmap_3d.py"):
    with open(path, "w", encoding="utf-8") as f:
        f.write(BLENDER_KRIRKRUTZ3D_SCRIPT)
    return path

# ---------- CLI ----------
def build_parser():
    p = argparse.ArgumentParser(description="Analyze image, call lionsmapper, emit Blender lithophane script.")
    p.add_argument("image", help="image path (map.png)")
    p.add_argument("--top", type=int, default=0, help="top N colors (0=all)")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--out-prefix", default=None)
    p.add_argument("--csv", action="store_true")
    p.add_argument("--emit-blender", action="store_true")
    p.add_argument("--no-embed", action="store_true")
    return p

def main():
    args = build_parser().parse_args()
    image_path = args.image
    if not os.path.exists(image_path):
        print("Image not found:", image_path); sys.exit(2)
    base = args.out_prefix if args.out_prefix else os.path.splitext(os.path.basename(image_path))[0]
    out_json = base + ".colors.json"
    out_csv = base + ".colors.csv"
    out_svg = base + ".svg"
    out_md = base + ".report.md"; out_txt = base + ".report.txt"
    top_n = args.top if args.top>0 else None
    print("Analyzing:", image_path)
    colors_list, img_size = analyze_colors(image_path, top_n=top_n)
    print("Found color entries:", len(colors_list))
    results = run_threaded(image_path, colors_list, workers=args.threads)
    # inject params automatically (tweak base numbers if you prefer)
    results = auto_inject_params(results, base_height=0.02, base_solidify=0.5, base_sample=4)
    wrapper = {
        "image": os.path.basename(image_path),
        "image_size": {"width": img_size[0], "height": img_size[1]},
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "lionsmapper_available": bool(LIONS_AVAILABLE),
        "colors": results
    }
    save_json(wrapper, out_json)
    print("Saved JSON:", out_json)
    if args.csv:
        save_csv(results, out_csv); print("Saved CSV:", out_csv)
    create_svg(image_path, results, img_size, out_svg, embed=not args.no_embed)
    print("Saved SVG:", out_svg)
    save_reports(results, out_md, out_txt, os.path.basename(image_path), img_size)
    print("Saved reports:", out_md, out_txt)
    if args.emit_blender:
        path = emit_blender_script("bitmap_3d.py")
        print("Emitted Blender script:", path)
        print("Run in Blender: blender --background --python bitmap_3d.py --", out_json, "--image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.6 --export-format obj")
    print("Done.")

if __name__ == "__main__":
    main()




