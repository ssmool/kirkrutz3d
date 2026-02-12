# bitmap_3d.py
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
    p.add_argument("results_json", default="result.colors.json")
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
    with open(args.results_json,'r',encoding='utf-8') as f:
        data=json.load(f)
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
        x_coord = px
        y_coord = py
        z_coord = 1.0 # Z-coordinate is necessary in 3D space
        bpy.ops.mesh.primitive_cube_add(
            enter_editmode=False,
            align='WORLD',
            location=(x_coord, y_coord, z_coord)
        )
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
        if export_fmt == "obj": bpy.ops.wm.obj_export(filepath=outfile)
        elif export_fmt == "stl": bpy.ops.wm.obj_export(filepath=outfile)
        print("Exported", outfile)

if __name__ == "__main__": main()
