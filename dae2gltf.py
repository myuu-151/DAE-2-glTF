#!/usr/bin/env python3
# dae2gltf — convert COLLADA (.dae) to glTF binary (.glb) via Blender, headless.
#
# Blender does the hard part (COLLADA skin/animation parsing + glTF skinning
# export), so rigged/animated meshes survive the round-trip instead of coming
# out as static geometry.
#
# Usage (run through Blender, NOT plain python):
#
#   # single file -> writes model.glb next to model.dae
#   blender --background --python dae2gltf.py -- model.dae
#
#   # single file, explicit output
#   blender --background --python dae2gltf.py -- model.dae out/model.glb
#
#   # batch: convert every .dae in a folder (recursively) to .glb beside it
#   blender --background --python dae2gltf.py -- ./models --batch
#
# On Windows, "blender" is usually:
#   "C:\Program Files\Blender Foundation\Blender 4.x\blender.exe"
#
# Exports .glb with skins + animations + tangents so it imports as a rig.

import bpy
import os
import sys
import glob


def reset_scene():
    """Empty the scene so each conversion starts clean."""
    bpy.ops.wm.read_factory_settings(use_empty=True)


def import_dae(path):
    if not hasattr(bpy.ops.wm, "collada_import"):
        raise RuntimeError(
            "This Blender build has no COLLADA importer. Enable the "
            "'Collada' / 'Import-Export: Collada' add-on, or use a Blender "
            "version that ships it (4.x has it in maintenance mode).")
    bpy.ops.wm.collada_import(filepath=path)


def export_glb(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=path,
        export_format='GLB',
        export_skins=True,          # keep the rig
        export_animations=True,     # keep the clips
        export_def_bones=False,     # export all bones, not just deform
        export_yup=True,            # glTF is Y-up
        export_apply=False,         # don't apply modifiers (preserve the rig)
        export_tangents=True,
        export_normals=True,
        export_texcoords=True,
        export_materials='EXPORT',
    )


def convert_one(dae_path, glb_path=None):
    if glb_path is None:
        glb_path = os.path.splitext(dae_path)[0] + ".glb"
    print("[dae2gltf] %s -> %s" % (dae_path, glb_path))
    reset_scene()
    import_dae(dae_path)
    export_glb(glb_path)
    return glb_path


def main():
    # Args after the "--" separator belong to us, not to Blender.
    argv = sys.argv
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    batch = "--batch" in args
    args = [a for a in args if a != "--batch"]

    if not args:
        print("usage: blender --background --python dae2gltf.py -- "
              "<input.dae | folder> [output.glb] [--batch]")
        sys.exit(1)

    inp = args[0]
    out = args[1] if len(args) > 1 else None

    if batch or os.path.isdir(inp):
        files = sorted(glob.glob(os.path.join(inp, "**", "*.dae"), recursive=True))
        if not files:
            print("[dae2gltf] no .dae files under %s" % inp)
            sys.exit(1)
        ok = 0
        for f in files:
            try:
                convert_one(f)
                ok += 1
            except Exception as e:
                print("[dae2gltf] FAILED %s: %s" % (f, e))
        print("[dae2gltf] done: %d/%d converted" % (ok, len(files)))
    else:
        try:
            convert_one(inp, out)
            print("[dae2gltf] done")
        except Exception as e:
            print("[dae2gltf] FAILED: %s" % e)
            sys.exit(1)


if __name__ == "__main__":
    main()
