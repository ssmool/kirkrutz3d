

Perfect — below is the final Blender lithophane script with automatic transfer.sh upload integrated (transfer.sh is the default method, per your choice). After the script finishes exporting the combined GLB and sprite-sheet PNG, it will attempt to upload them to transfer.sh and print the returned public URLs in Blender’s console.

Notes:

    The script tries to use requests for upload (faster & cleaner). If requests is not available in Blender’s Python, it falls back to urllib (which should work in modern Blender Python builds).

    If you prefer S3 or Gist later, the uploader function can be extended — but transfer.sh is implemented now as requested.

    Save this as image_to_3d_blender_lithophane_final_with_upload.py and run inside Blender the same way as previous examples. The new flags are --upload (default on) and --upload-method (defaults to transfer).


# image_to_3d_blender_lithophane_final_with_upload.py
# Final Blender script with automatic upload to transfer.sh (default).
#
# Usage (example):
# blender --background --python image_to_3d_blender_lithophane_final_with_upload.py -- map.colors.json \
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

import bpy
import os
import sys
import json
import math
import traceback
from mathutils import Vector

# ----------------- CLI -----------------
def parse_argv():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--")+1:]
    else:
        argv = []
    import argparse
    p = argparse.ArgumentParser(description="Lithophane generator + auto-upload (default transfer.sh)")
    p.add_argument("results_json", help="Analyzer JSON (e.g., map.colors.json)")
    p.add_argument("--image-dir", default=".", help="Directory containing the original image")
    p.add_argument("--out-dir", default="./blender_out", help="Output directory")
    p.add_argument("--sample", type=int, default=4, help="Downsample factor (every Nth pixel)")
    p.add_argument("--height-scale", type=float, default=0.02, help="Base height multiplier")
    p.add_argument("--rgb-tolerance", type=float, default=12.0, help="RGB Euclidean distance tolerance")
    p.add_argument("--solidify", type=float, default=0.5, help="Solidify thickness")
    p.add_argument("--export-format", default="obj", choices=["obj","stl"], help="Per-object export format")
    p.add_argument("--max-colors", type=int, default=0, help="Limit number of colors processed (0 = all)")
    p.add_argument("--export-combined", default=None, choices=["glb","gltf","obj","none"], help="Export combined file with all objects (glb recommended)")
    p.add_argument("--render-preview", action="store_true", help="Render perspective previews (per-color and combined)")
    p.add_argument("--render-ortho", action="store_true", help="Render orthographic top-down previews")
    p.add_argument("--preview-size", type=int, default=1024, help="Thumbnail size in px")
    p.add_argument("--render-samples", type=int, default=32, help="Render samples for Cycles")
    p.add_argument("--sprite-sheet", action="store_true", help="Compose sprite sheet from per-color previews (requires Pillow)")
    p.add_argument("--sprite-cols", type=int, default=4, help="Number of columns for sprite sheet grid")
    p.add_argument("--no-preview", action="store_true", help="Skip all previews (useful for only exporting geometry)")
    p.add_argument("--upload", action="store_true", default=True, help="Upload combined + sprite sheet after generation (default: True)")
    p.add_argument("--no-upload", action="store_true", help="Do not upload (overrides --upload)")
    p.add_argument("--upload-method", default="transfer", choices=["transfer"], help="Upload method to use (transfer = transfer.sh)")
    return p.parse_args(argv)

# ----------------- Helpers -----------------
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def load_image_bpy(path):
    try:
        img = bpy.data.images.load(path)
        if not img.has_data:
            _ = img.pixels[:]
        return img
    except Exception as e:
        print("ERROR loading image:", e)
        return None

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
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes; links = mat.node_tree.links
    nodes.clear()
    out = nodes.new(type='ShaderNodeOutputMaterial')
    bsdf = nodes.new(type='ShaderNodeBsdfPrincipled')
    bsdf.inputs['Base Color'].default_value = (rn,gn,bn,1.0)
    bsdf.inputs['Roughness'].default_value = 0.6
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
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], faces); mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj

def setup_cycles_render(preview_size=1024, samples=32):
    # camera & lights
    cam = bpy.data.cameras.get("LM_Camera")
    if cam is None:
        cam = bpy.data.cameras.new("LM_Camera")
        cam_obj = bpy.data.objects.new("LM_Camera", cam)
        bpy.context.collection.objects.link(cam_obj)
    cam_obj = bpy.data.objects.get("LM_Camera")
    if cam_obj is None:
        cam_obj = bpy.data.objects.new("LM_Camera", cam)
        bpy.context.collection.objects.link(cam_obj)
    # lights
    if "LM_Key" not in bpy.data.objects:
        kd = bpy.data.lights.new("LM_Key", type='AREA'); kd.energy = 800
        kobj = bpy.data.objects.new("LM_Key", kd); bpy.context.collection.objects.link(kobj); kobj.location=(0.6,-0.6,1.2)
    if "LM_Fill" not in bpy.data.objects:
        fd = bpy.data.lights.new("LM_Fill", type='AREA'); fd.energy = 250
        fobj = bpy.data.objects.new("LM_Fill", fd); bpy.context.collection.objects.link(fobj); fobj.location=(-0.6,-0.6,0.8)
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.render.resolution_x = preview_size; scene.render.resolution_y = preview_size
    scene.camera = cam_obj
    return cam_obj

# ----------------- Sprite-sheet composer -----------------
def compose_sprite_sheet(image_paths, thumb_size, cols, out_path):
    try:
        from PIL import Image
    except Exception:
        print("Pillow not available in Blender Python. Sprite sheet will not be composed. Install Pillow to enable it.")
        return False
    if not image_paths:
        print("No images to compose.")
        return False
    rows = math.ceil(len(image_paths) / cols)
    sheet_w = cols * thumb_size
    sheet_h = rows * thumb_size
    sheet = Image.new("RGBA", (sheet_w, sheet_h), (255,255,255,0))
    for idx, p in enumerate(image_paths):
        try:
            im = Image.open(p).convert("RGBA").resize((thumb_size, thumb_size), Image.LANCZOS)
            r = idx // cols; c = idx % cols
            sheet.paste(im, (c*thumb_size, r*thumb_size))
        except Exception as e:
            print("Warning: failed to open/paste", p, e)
    sheet.save(out_path)
    return True

# ----------------- transfer.sh uploader (requests preferred, urllib fallback) -----------------
def upload_transfer_sh(file_path):
    filename = os.path.basename(file_path)
    url = f"https://transfer.sh/{filename}"
    # try requests
    try:
        import requests
        with open(file_path, "rb") as f:
            r = requests.put(url, data=f)
        if r.status_code in (200,201):
            return r.text.strip()
        else:
            raise RuntimeError(f"transfer.sh upload failed: {r.status_code} {r.text}")
    except Exception as e_req:
        # fallback to urllib
        try:
            import urllib.request
            with open(file_path, "rb") as f:
                data = f.read()
            req = urllib.request.Request(url, data=data, method='PUT')
            req.add_header('Content-Type', 'application/octet-stream')
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = resp.read().decode().strip()
                return body
        except Exception as e_urllib:
            raise RuntimeError("Both requests and urllib upload attempts failed: requests_err=%s urllib_err=%s" % (str(e_req), str(e_urllib)))

# ----------------- Main workflow -----------------
def main():
    args = parse_argv()
    ensure_dir(args.out_dir)
    try:
        with open(args.results_json, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print("Failed to read JSON:", e); return

    image_name = data.get("image")
    if not image_name:
        print("JSON missing 'image'"); return
    img_path = os.path.join(args.image_dir, image_name)
    if not os.path.exists(img_path):
        print("Image file not found:", img_path); return
    img = load_image_bpy(img_path)
    if img is None:
        print("Failed to load image into Blender"); return
    w = img.size[0]; h = img.size[1]
    items = list(data.get("colors", {}).items())
    if args.max_colors > 0:
        items = items[:args.max_colors]

    combined_objs = []
    preview_files = []
    ortho_files = []

    gen_collection_name = "LM_Generated"
    if gen_collection_name in bpy.data.collections:
        gen_col = bpy.data.collections[gen_collection_name]
    else:
        gen_col = bpy.data.collections.new(gen_collection_name); bpy.context.scene.collection.children.link(gen_col)

    # generate objects and per-object exports
    for key, info in items:
        rgb = info.get("rgb", [255,255,255]); rgb = [int(x) for x in rgb]
        params = info.get("params", {}) or {}
        sample = int(params.get("sample", args.sample))
        height_scale = float(params.get("height_scale", args.height_scale))
        solidify = float(params.get("solidify", args.solidify))
        export_fmt = params.get("export_format", args.export_format)
        mat_name = params.get("material_name", None)

        print("Processing color:", rgb, "sample", sample, "height_scale", height_scale)
        wpts = max(2, w // sample); hpts = max(2, h // sample)
        grid = [[0.0 for _ in range(wpts)] for __ in range(hpts)]
        anymask = False
        for j in range(hpts):
            for i in range(wpts):
                px = min(w-1, i*sample); py = min(h-1, j*sample)
                pr,pg,pb,pa = img_pixel(img, px, py)
                if color_dist((pr,pg,pb), tuple(rgb)) <= args.rgb_tolerance:
                    br = brightness((pr,pg,pb)); hh = (1.0 - br) * height_scale
                    grid[j][i] = hh; anymask = True
                else:
                    grid[j][i] = 0.0
        if not anymask:
            print("Skipping color", rgb, "- no masked pixels")
            continue
        name = f"color_{rgb[0]}_{rgb[1]}_{rgb[2]}"
        obj = build_grid_mesh(name, grid, wpts, hpts, sample)
        if obj.name not in gen_col.objects:
            gen_col.objects.link(obj)
        bpy.context.view_layer.update()
        bbox = [Vector(b) for b in obj.bound_box]
        minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
        miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
        centerx = (minx + maxx) / 2.0; centery = (miny + maxy) / 2.0
        obj.location = (-centerx, -centery, 0.0)
        mat = create_material(rgb, name=mat_name)
        if obj.data.materials: obj.data.materials[0] = mat
        else: obj.data.materials.append(mat)
        mod = obj.modifiers.new(name="LM_Solidify", type='SOLIDIFY'); mod.thickness = solidify; mod.offset = 1.0
        for f in obj.data.polygons: f.use_smooth = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # export per-object
        out_single = os.path.join(args.out_dir, name + "." + export_fmt)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        try:
            if export_fmt == "obj":
                bpy.ops.export_scene.obj(filepath=out_single, use_selection=True, use_materials=True)
            elif export_fmt == "stl":
                bpy.ops.export_mesh.stl(filepath=out_single, use_selection=True)
            print("Exported individual:", out_single)
        except Exception as e:
            print("Warning: failed to export individual object:", e)
        combined_objs.append(obj)

    combined_path = None
    sprite_path = None

    # Combined export
    if args.export_combined and args.export_combined != "none" and combined_objs:
        bpy.ops.object.select_all(action='DESELECT')
        for o in combined_objs: o.select_set(True)
        out_combined = os.path.join(args.out_dir, "combined." + args.export_combined)
        try:
            if args.export_combined in ("glb", "gltf"):
                export_as_glb = True if args.export_combined == "glb" else False
                bpy.ops.export_scene.gltf(filepath=out_combined, use_selection=True,
                                         export_format='GLB' if export_as_glb else 'GLTF_SEPARATE',
                                         export_materials='EXPORT')
            elif args.export_combined == "obj":
                bpy.ops.export_scene.obj(filepath=out_combined, use_selection=True, use_materials=True)
            print("Exported combined:", out_combined)
            combined_path = out_combined
        except Exception as e:
            print("Warning: combined export failed:", e)

    # Previews
    preview_files = []
    ortho_files = []
    if not args.no_preview and args.render_preview:
        cam = setup_cycles_render(preview_size=args.preview_size, samples=args.render_samples)
        # combined perspective preview
        if combined_objs:
            all_points = []
            for o in combined_objs:
                for b in o.bound_box:
                    all_points.append(Vector(b) + o.location)
            if all_points:
                min_x = min(v.x for v in all_points); max_x = max(v.x for v in all_points)
                min_y = min(v.y for v in all_points); max_y = max(v.y for v in all_points)
                min_z = min(v.z for v in all_points); max_z = max(v.z for v in all_points)
                center = Vector(((min_x+max_x)/2.0, (min_y+max_y)/2.0, (min_z+max_z)/2.0))
                span = max(max_x-min_x, max_y-min_y, 0.001)
                cam.location = (center.x, center.y - span*1.5, center.z + span*0.6)
                cam.rotation_euler = (math.radians(75), 0, 0)
        combined_preview_path = os.path.join(args.out_dir, "preview_combined_persp.png")
        bpy.context.scene.render.filepath = combined_preview_path
        try:
            bpy.ops.render.render(write_still=True)
            print("Saved combined perspective preview:", combined_preview_path)
        except Exception as e:
            print("Warning: failed to render combined preview:", e)

        # per-color perspective previews
        for o in combined_objs:
            try:
                bpy.ops.object.select_all(action='DESELECT')
                o.select_set(True); bpy.context.view_layer.objects.active = o
                bbox = [Vector(b) + o.location for b in o.bound_box]
                minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
                miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
                minz = min(v.z for v in bbox); maxz = max(v.z for v in bbox)
                center = Vector(((minx+maxx)/2.0, (miny+maxy)/2.0, (minz+maxz)/2.0))
                span = max(maxx-minx, maxy-miny, 0.001)
                cam.location = (center.x, center.y - span*1.5, center.z + span*0.6)
                cam.rotation_euler = (math.radians(75), 0, 0)
                out_png = os.path.join(args.out_dir, f"preview_{o.name}_persp.png")
                bpy.context.scene.render.filepath = out_png
                bpy.ops.render.render(write_still=True)
                preview_files.append(out_png)
                print("Saved preview:", out_png)
            except Exception as e:
                print("Warning: failed to render preview for", o.name, e)

    # Orthographic previews
    if not args.no_preview and args.render_ortho:
        cam = bpy.data.objects.get("LM_Camera")
        if cam is None:
            cam = setup_cycles_render(preview_size=args.preview_size, samples=args.render_samples)
        cam_obj = cam
        # Combined ortho
        if combined_objs:
            all_bbox_points = []
            for o in combined_objs:
                for b in o.bound_box:
                    all_bbox_points.append(Vector(b) + o.location)
            if all_bbox_points:
                min_x = min(v.x for v in all_bbox_points); max_x = max(v.x for v in all_bbox_points)
                min_y = min(v.y for v in all_bbox_points); max_y = max(v.y for v in all_bbox_points)
                min_z = min(v.z for v in all_bbox_points); max_z = max(v.z for v in all_bbox_points)
                center = Vector(((min_x+max_x)/2.0, (min_y+max_y)/2.0, (min_z+max_z)/2.0))
                span = max(max_x-min_x, max_y-min_y, 0.001)
                cam_obj.data.type = 'ORTHO'
                cam_obj.location = (center.x, center.y, center.z + span*2.2)
                cam_obj.rotation_euler = (math.radians(0), 0, 0)
                cam_obj.data.ortho_scale = span * 1.5
                out_comb_ortho = os.path.join(args.out_dir, "preview_combined_ortho.png")
                bpy.context.scene.render.filepath = out_comb_ortho
                try:
                    bpy.ops.render.render(write_still=True)
                    ortho_files.append(out_comb_ortho)
                    print("Saved combined orthographic preview:", out_comb_ortho)
                except Exception as e:
                    print("Warning: failed to render combined ortho preview:", e)
        # per-color ortho
        for o in combined_objs:
            try:
                bbox = [Vector(b) + o.location for b in o.bound_box]
                minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
                miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
                minz = min(v.z for v in bbox); maxz = max(v.z for v in bbox)
                center = Vector(((minx+maxx)/2.0, (miny+maxy)/2.0, (minz+maxz)/2.0))
                span = max(maxx-minx, maxy-miny, 0.001)
                cam_obj.data.type = 'ORTHO'
                cam_obj.location = (center.x, center.y, center.z + span*2.2)
                cam_obj.rotation_euler = (math.radians(0), 0, 0)
                cam_obj.data.ortho_scale = span * 1.5
                out_png = os.path.join(args.out_dir, f"preview_{o.name}_ortho.png")
                bpy.context.scene.render.filepath = out_png
                bpy.ops.render.render(write_still=True)
                ortho_files.append(out_png)
                print("Saved orthographic preview:", out_png)
            except Exception as e:
                print("Warning: failed to render ortho preview for", o.name, e)

    # Sprite sheet composition
    if args.sprite_sheet:
        thumbs = preview_files[:] if preview_files else ortho_files[:]
        if thumbs:
            sprite_out = os.path.join(args.out_dir, "sprite_sheet.png")
            ok = compose_sprite_sheet(thumbs, args.preview_size, args.sprite_cols, sprite_out)
            if ok:
                sprite_path = sprite_out
                print("Saved sprite sheet:", sprite_path)
            else:
                print("Sprite sheet composition failed or Pillow missing.")
        else:
            print("No previews available to compose sprite sheet.")

    # Automatic upload (transfer.sh) if requested and not explicitly disabled
    if (args.upload and not args.no_upload):
        uploaded = {}
        to_upload = []
        if combined_path:
            to_upload.append(combined_path)
        elif combined_path is None and args.export_combined and args.export_combined != "none":
            # if combined was requested but failed, skip
            pass
        # prefer sprite_path else try common filename
        if sprite_path:
            to_upload.append(sprite_path)
        else:
            candidate = os.path.join(args.out_dir, "sprite_sheet.png")
            if os.path.exists(candidate):
                to_upload.append(candidate)
        # also include combined preview images if any
        candidate_preview = os.path.join(args.out_dir, "preview_combined_persp.png")
        if os.path.exists(candidate_preview):
            to_upload.append(candidate_preview)
        # filter unique and existing
        to_upload = [p for i,p in enumerate(to_upload) if p and os.path.exists(p)]
        if not to_upload:
            print("No files found to upload.")
        else:
            print("Uploading files to transfer.sh (default)...")
            for fpath in to_upload:
                try:
                    url = upload_transfer_sh(fpath)
                    uploaded[fpath] = {"status":"ok", "url": url}
                    print("Uploaded:", fpath, "->", url)
                except Exception as e:
                    uploaded[fpath] = {"status":"error", "error": str(e)}
                    print("Upload failed for", fpath, ":", e)
            # print JSON summary to Blender console
            try:
                import json as _json
                print("Upload summary:", _json.dumps(uploaded, indent=2))
            except Exception:
                pass

    print("Script completed.")

if __name__ == "__main__":
    # ensure script arguments parsed and execute
    try:
        main()
    except Exception:
        print("Fatal error in script:")
        traceback.print_exc()



