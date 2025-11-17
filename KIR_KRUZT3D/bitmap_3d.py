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

import bpy, os, sys, json, math
from mathutils import Vector

# ----------------- arg parsing -----------------
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
    p.add_argument("--export-combined", default=None, choices=["glb","gltf","obj","none"])
    p.add_argument("--render-preview", action="store_true")
    p.add_argument("--preview-size", type=int, default=1024)
    p.add_argument("--render-samples", type=int, default=32)
    return p.parse_args(argv)

# ----------------- helpers -----------------
def ensure_dir(p):
    os.makedirs(p, exist_ok=True)

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

def setup_render_scene(preview_size=1024, samples=32):
    # remove existing camera and lights we create (we keep safety)
    # create camera
    cam = bpy.data.objects.new("LM_Camera", bpy.data.cameras.new("LM_Camera"))
    bpy.context.collection.objects.link(cam)
    cam.location = (0.0, -1.0, 0.7)
    cam.data.lens = 50
    cam.rotation_euler = (math.radians(75), 0, 0)
    # create lights - key + fill
    light_data = bpy.data.lights.new(name="LM_Key", type='AREA')
    light_data.energy = 800
    light = bpy.data.objects.new(name="LM_Key", object_data=light_data)
    bpy.context.collection.objects.link(light)
    light.location = (0.6, -0.6, 1.2)
    light.data.size = 0.8
    # fill light
    l2_data = bpy.data.lights.new(name="LM_Fill", type='AREA')
    l2_data.energy = 250
    l2 = bpy.data.objects.new(name="LM_Fill", object_data=l2_data)
    bpy.context.collection.objects.link(l2)
    l2.location = (-0.6, -0.6, 0.8)
    l2.data.size = 1.0
    # world
    bpy.context.scene.world.use_nodes = True
    # render settings
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = samples
    scene.render.resolution_x = preview_size
    scene.render.resolution_y = preview_size
    scene.camera = cam
    return cam

# ----------------- main -----------------
def main():
    args = parse_argv()
    ensure_dir(args.out_dir)
    with open(args.results_json, 'r', encoding='utf-8') as f:
        data = json.load(f)
    image_name = data.get("image")
    if not image_name:
        print("JSON missing 'image'"); return
    img_path = os.path.join(args.image_dir, image_name)
    if not os.path.exists(img_path):
        print("Image not found:", img_path); return
    img = load_image_bpy(img_path); w,h = img.size[0], img.size[1]
    items = list(data.get("colors", {}).items())
    if args.max_colors>0: items = items[:args.max_colors]

    combined_objs = []  # list of objects to combine
    # iterate colors
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
        # center
        bpy.context.view_layer.update()
        bbox=[Vector(b) for b in obj.bound_box]
        minx=min(v.x for v in bbox); maxx=max(v.x for v in bbox); miny=min(v.y for v in bbox); maxy=max(v.y for v in bbox)
        centerx = (minx+maxx)/2.0; centery=(miny+maxy)/2.0
        obj.location = (-centerx, -centery, 0.0)
        # material
        mat = create_material(rgb, name=mat_name)
        if obj.data.materials: obj.data.materials[0]=mat
        else: obj.data.materials.append(mat)
        # solidify
        mod = obj.modifiers.new(name="LM_Solidify", type='SOLIDIFY'); mod.thickness = solidify; mod.offset=1.0
        for f in obj.data.polygons: f.use_smooth=True
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.modifier_apply(modifier=mod.name)
        # export single file per-object (if requested)
        out_single = os.path.join(args.out_dir, name + "." + export_fmt)
        bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active = obj
        if export_fmt == "obj":
            bpy.ops.export_scene.obj(filepath=out_single, use_selection=True, use_materials=True)
        elif export_fmt == "stl":
            bpy.ops.export_mesh.stl(filepath=out_single, use_selection=True)
        print("Exported", out_single)
        combined_objs.append(obj)

    # COMBINED EXPORT (one file with all objects + materials)
    if args.export_combined and args.export_combined != "none" and combined_objs:
        # create a new collection to gather objects
        colname = "LM_Combined_Collection"
        if colname in bpy.data.collections:
            col = bpy.data.collections[colname]
        else:
            col = bpy.data.collections.new(colname); bpy.context.scene.collection.children.link(col)
        for o in combined_objs:
            if o.name not in col.objects:
                col.objects.link(o)
        # select all combined objects
        bpy.ops.object.select_all(action='DESELECT')
        for o in combined_objs:
            o.select_set(True)
        out_comb = os.path.join(args.out_dir, "combined." + args.export_combined)
        if args.export_combined == "glb" or args.export_combined == "gltf":
            bpy.ops.export_scene.gltf(filepath=out_comb, use_selection=True, export_format='GLB' if args.export_combined=="glb" else 'GLTF_SEPARATE', export_materials='EXPORT')
        elif args.export_combined == "obj":
            bpy.ops.export_scene.obj(filepath=out_comb, use_selection=True, use_materials=True)
        print("Exported combined file:", out_comb)

    # RENDER PREVIEWS
    if args.render_preview:
        cam = setup_render_scene(preview_size=args.preview_size, samples=args.render_samples)
        # Combined render (all visible)
        # place camera at a good distance: compute bounding box for combined_objs
        if combined_objs:
            minx=min( (min((v.x for v in o.bound_box), default=0) for o in combined_objs) )
        # center camera on scene
        # for simpler approach: compute scene bounding box by all objects
        all_bbox_points = []
        for o in combined_objs:
            for b in o.bound_box:
                all_bbox_points.append(Vector(b) + o.location)
        if all_bbox_points:
            min_x = min(v.x for v in all_bbox_points); max_x = max(v.x for v in all_bbox_points)
            min_y = min(v.y for v in all_bbox_points); max_y = max(v.y for v in all_bbox_points)
            min_z = min(v.z for v in all_bbox_points); max_z = max(v.z for v in all_bbox_points)
            scene_center = Vector(((min_x+max_x)/2.0, (min_y+max_y)/2.0, (min_z+max_z)/2.0))
            # position camera based on largest dimension
            span_x = max_x - min_x; span_y = max_y - min_y; span = max(span_x, span_y, 0.001)
            # set camera location relatively
            cam.location = (scene_center.x, scene_center.y - span*1.5, scene_center.z + span*0.6)
            cam.rotation_euler = (math.radians(75), 0, 0)
        # render combined
        combined_png = os.path.join(args.out_dir, "preview_combined.png")
        bpy.context.scene.render.filepath = combined_png
        bpy.ops.render.render(write_still=True)
        print("Saved combined preview:", combined_png)
        # render per-color thumbs (isolate each object)
        for o in combined_objs:
            bpy.ops.object.select_all(action='DESELECT')
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            # position camera centered on object bounding box
            bbox = [Vector(b) + o.location for b in o.bound_box]
            minx = min(v.x for v in bbox); maxx = max(v.x for v in bbox)
            miny = min(v.y for v in bbox); maxy = max(v.y for v in bbox)
            minz = min(v.z for v in bbox); maxz = max(v.z for v in bbox)
            center = Vector(((minx+maxx)/2.0, (miny+maxy)/2.0, (minz+maxz)/2.0))
            span = max(maxx-minx, maxy-miny, 0.001)
            cam.location = (center.x, center.y - span*1.5, center.z + span*0.6)
            cam.rotation_euler = (math.radians(75), 0, 0)
            out_png = os.path.join(args.out_dir, f"preview_{o.name}.png")
            bpy.context.scene.render.filepath = out_png
            bpy.ops.render.render(write_still=True)
            print("Saved preview:", out_png)

if __name__ == "__main__":
    main()

