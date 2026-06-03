# DAE-2-glTF

Convert **COLLADA `.dae` → glTF binary `.glb`** using Blender in headless mode.

Blender handles the hard parts of COLLADA (skinning via `<controller>`/`<skin>`,
animation channels) and writes proper glTF skinning on the way out, so **rigged
and animated models survive the conversion** instead of collapsing to static
geometry.

## Requirements

- [Blender](https://www.blender.org/) 4.x (any build that ships the COLLADA
  importer — it's included, in maintenance mode).

No Python packages to install; the script runs *inside* Blender.

## Usage

Run it through Blender, not plain Python:

```sh
# single file -> writes model.glb next to model.dae
blender --background --python dae2gltf.py -- model.dae

# single file, explicit output
blender --background --python dae2gltf.py -- model.dae out/model.glb

# batch: convert every .dae under a folder (recursive) to .glb beside it
blender --background --python dae2gltf.py -- ./models --batch
```

On Windows, `blender` is usually:

```
"C:\Program Files\Blender Foundation\Blender 4.x\blender.exe"
```

So a full Windows invocation looks like:

```
"C:\Program Files\Blender Foundation\Blender 4.x\blender.exe" --background --python dae2gltf.py -- model.dae
```

## What it exports

`.glb` (binary glTF) with:

- **Skins** — the armature/rig is preserved.
- **Animations** — all clips.
- Normals, tangents, texcoords, and materials.
- Y-up (glTF convention).

Each file is converted in a fresh, empty scene, so batch runs don't bleed into
each other. Failed files are reported and skipped (the batch keeps going).

## Why Blender instead of a from-scratch parser

COLLADA is a sprawling format and its skinning/animation are the fiddly bits.
Re-implementing that correctly is a large, brittle undertaking; Blender already
does it well, so this is a thin, reliable wrapper around it.

If you don't want a Blender dependency, [`assimp`](https://github.com/assimp/assimp)
can also do it in one line (`assimp export in.dae out.glb`), though its glTF
skin export is less consistent.

## License

MIT.
