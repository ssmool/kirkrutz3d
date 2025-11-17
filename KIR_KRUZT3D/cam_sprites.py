"""cli:1.Produce combined GLB + previews for map.colors.json:
blender --background --python bitmap_3d.py -- map.colors.json --image-dir . --out-dir ./blender_out \
  --sample 4 --height-scale 0.02 --rgb-tolerance 12 --solidify 0.6 --export-format obj \
  --export-combined glb --render-preview --preview-size 1024 --render-samples 64"""

"""cli:2.Only combined export (no individual exports, no previews):
blender --background --python bitmap_3d.py -- map.colors.json --image-dir . --out-dir ./blender_out \
  --export-combined glb"""

"""cli:blender --background --python bitmap_3d_final.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out --sample 4 --height-scale 0.02 --rgb-tolerance 12 \
  --solidify 0.6 --export-format obj --export-combined glb --render-preview --render-ortho \
  --preview-size 1024 --render-samples 64 --sprite-sheet --sprite-cols 4"""

#Only combined export, no renders:

"""cli:blender --background --python bitmap_3d_final.py -- map.colors.json \
  --image-dir . --out-dir ./blender_out --export-combined glb --no-preview"""

# bitmap_3d_final.py
# Final script: combined GLB, per-color previews, orthographic top-down renders, and sprite-sheet (1024 px thumbs)
#
# Run in Blender:
# blender --background --python bitmap_3d.py -- results.colors.json --image-dir . --out-dir ./blender_out --export-combined glb --render-preview --sprite-sheet --sprite-cols 4
#

import bpy
import os
import sys
import json
import math
from mathutils import Vector

# -------------- Arguments --------------
def parse_argv():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--")+1:]
    else:
        argv = []
    import argparse
    p = argparse.ArgumentParser(description="Lithophane generator: combined GLB + previews + sprite sheet (1024px thumbs)")
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
    p.add_argument("--preview-size", type=int, default=1024, help="Thumbnail size in px (you chose 1024)")
    p.add_argument("--render-samples", type=int, default=32, help="Render samples for Cycles")
    p.add_argument("--sprite-sheet", action="store_true", help="Compose sprite sheet from per-color previews (requires Pillow)")
    p.add_argument("--sprite-cols", type=int, default=4, help="Number of columns for sprite sheet grid")
    p.add_argument("--no-preview", action="store_true", help="Skip all previews (useful for only exporting geometry)")
    return p.parse_args(argv)

# -------------- Helpers --------------
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
    # add camera & lights (remove previously created LM_* to avoid duplicates)
    for o in list(bpy.data.objects):
        if o.name.startswith("LM_Cam") or o.name.startswith("LM_Key") or o.name.startswith("LM_Fill"):
            # leave existing if present
            pass
    cam = bpy.data.cameras.get("LM_Camera")
    if cam is None:
        cam = bpy.data.cameras.new("LM_Camera")
        cam_obj = bpy.data.objects.new("LM_Camera", cam)
        bpy.context.collection.objects.link(cam_obj)
    cam_obj = bpy.data.objects.get("LM_Camera")
    if cam_obj is None:
        cam_obj = bpy.data.objects.new("LM_Camera", cam)
        bpy.context.collection.objects.link(cam_obj)
    # ensure a key light
    if "LM_Key" not in bpy.data.objects:
        kd = bpy.data.lights.new("LM_Key", type='AREA')
        kd.energy = 800
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

# -------------- Sprite sheet helper (uses Pillow if available) --------------
def compose_sprite_sheet(image_paths, thumb_size, cols, out_path):
    try:
        from PIL import Image
    except Exception:
        print("Pillow not available in Blender Python. Sprite sheet will not be composed. Install Pillow in Blender's Python to enable this.")
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

# -------------- Main --------------
def main():
    args = parse_argv()
    ensure_dir(args.out_dir)
    # load JSON
    with open(args.results_json, "r", encoding="utf-8") as f:
        data = json.load(f)
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

    # Create a clean little collection for generated objects
    coll_name = "LM_Generated"
    if coll_name in bpy.data.collections:
        gen_col = bpy.data.collections[coll_name]
    else:
        gen_col = bpy.data.collections.new(coll_name); bpy.context.scene.collection.children.link(gen_col)

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
        # move into generated collection
        if obj.name not in gen_col.objects:
            gen_col.objects.link(obj)
        # center object
        bpy.context.view_layer.update()
        bbox = [Vector(b) for b in obj.bound_box]
        minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
        miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
        centerx = (minx + maxx) / 2.0; centery = (miny + maxy) / 2.0
        obj.location = (-centerx, -centery, 0.0)
        # material
        mat = create_material(rgb, name=mat_name)
        if obj.data.materials: obj.data.materials[0] = mat
        else: obj.data.materials.append(mat)
        # solidify
        mod = obj.modifiers.new(name="LM_Solidify", type='SOLIDIFY'); mod.thickness = solidify; mod.offset = 1.0
        for f in obj.data.polygons: f.use_smooth = True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # per-object export
        out_single = os.path.join(args.out_dir, name + "." + export_fmt)
        bpy.ops.object.select_all(action='DESELECT')
        obj.select_set(True); bpy.context.view_layer.objects.active = obj
        if export_fmt == "obj":
            bpy.ops.export_scene.obj(filepath=out_single, use_selection=True, use_materials=True)
        elif export_fmt == "stl":
            bpy.ops.export_mesh.stl(filepath=out_single, use_selection=True)
        print("Exported individual:", out_single)
        combined_objs.append(obj)

    # Combined export (single GLB/GLTF/OBJ)
    if args.export_combined and args.export_combined != "none" and combined_objs:
        bpy.ops.object.select_all(action='DESELECT')
        for o in combined_objs:
            o.select_set(True)
        out_combined = os.path.join(args.out_dir, "combined." + args.export_combined)
        if args.export_combined in ("glb", "gltf"):
            export_as_glb = True if args.export_combined == "glb" else False
            bpy.ops.export_scene.gltf(filepath=out_combined, use_selection=True,
                                     export_format='GLB' if export_as_glb else 'GLTF_SEPARATE',
                                     export_materials='EXPORT')
        elif args.export_combined == "obj":
            bpy.ops.export_scene.obj(filepath=out_combined, use_selection=True, use_materials=True)
        print("Exported combined:", out_combined)

    # Previews: perspective + orthographic (top-down)
    if not args.no_preview and args.render_preview:
        cam = setup_cycles_render(preview_size=args.preview_size, samples=args.render_samples)
        # combined preview (all visible)
        if combined_objs:
            # compute scene center
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
        bpy.ops.render.render(write_still=True)
        print("Saved combined perspective preview:", combined_preview_path)

        # per-color perspective previews
        for o in combined_objs:
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

    # Orthographic top-down previews
    if not args.no_preview and args.render_ortho:
        # create/set camera orthographic
        cam = bpy.data.objects.get("LM_Camera")
        if cam is None:
            cam = setup_cycles_render(preview_size=args.preview_size, samples=args.render_samples)
        cam.data.type = 'PERSP' if getattr(cam.data, 'type', None) is None else cam.data.type
        # render combined ortho
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
                # set camera to orthographic and place high above
                cam.data.type = 'ORTHO'
                cam.location = (center.x, center.y, center.z + span*2.2)
                cam.rotation_euler = (math.radians(0), 0, 0)
                # orthographic scale to cover entire span (padding factor)
                cam.data.ortho_scale = span * 1.5
                out_comb_ortho = os.path.join(args.out_dir, "preview_combined_ortho.png")
                bpy.context.scene.render.filepath = out_comb_ortho
                bpy.ops.render.render(write_still=True)
                ortho_files.append(out_comb_ortho)
                print("Saved combined orthographic preview:", out_comb_ortho)
        # per-color ortho previews
        for o in combined_objs:
            bbox = [Vector(b) + o.location for b in o.bound_box]
            minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
            miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
            minz = min(v.z for v in bbox); maxz = max(v.z for v in bbox)
            center = Vector(((minx+maxx)/2.0, (miny+maxy)/2.0, (minz+maxz)/2.0))
            span = max(maxx-minx, maxy-miny, 0.001)
            cam.data.type = 'ORTHO'
            cam.location = (center.x, center.y, center.z + span*2.2)
            cam.rotation_euler = (math.radians(0), 0, 0)
            cam.data.ortho_scale = span * 1.5
            out_png = os.path.join(args.out_dir, f"preview_{o.name}_ortho.png")
            bpy.context.scene.render.filepath = out_png
            bpy.ops.render.render(write_still=True)
            ortho_files.append(out_png)
            print("Saved orthographic preview:", out_png)

    # Sprite sheet: compose per-color perspective previews (if requested)
    if args.sprite_sheet:
        # prefer perspective per-color previews; if none exist, try ortho files
        thumbs = preview_files[:] if preview_files else ortho_files[:]
        if not thumbs:
            print("No previews available to compose sprite sheet.")
        else:
            sprite_out = os.path.join(args.out_dir, "sprite_sheet.png")
            # thumbs should be at preview_size; we will attempt to compose them into sheet using Pillow
            sheet_ok = compose_sprite_sheet(thumbs, args.preview_size, args.sprite_cols, sprite_out)
            if sheet_ok:
                print("Saved sprite sheet:", sprite_out)
            else:
                print("Sprite sheet not created (Pillow missing or error). Individual previews are available.")

    print("All done.")

if __name__ == "__main__":
    main()

