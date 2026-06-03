# DAE-2-glTF

A small **GUI** that converts COLLADA `.dae` files to glTF binary `.glb`.

Add your `.dae` files, click **Convert**, get `.glb` out. **Skinning and
animation are preserved**, so rigged models stay rigged.

![flow](https://img.shields.io/badge/.dae-%E2%86%92%20.glb-blue)

## Run

```sh
python dae2gltf.py
```

(On Windows you can also just double-click `dae2gltf.py`.)

Needs **Python 3** with Tkinter — that ships with the standard Python installer
on Windows/macOS; on Linux install `python3-tk`.

## How it works (and what it needs)

The actual COLLADA→glTF conversion is done by **Blender in the background** —
reimplementing skinned-COLLADA parsing from scratch is large and brittle, while
Blender already does it well. So the GUI is a friendly front-end that drives a
Blender install for you:

- It **auto-detects** Blender (PATH + the usual install folders).
- If it can't find it, click **Browse…** and point it at `blender.exe`
  (Windows) / the `Blender` binary (macOS/Linux).
- You never have to open Blender or write a script — the GUI runs it headless.

[Download Blender](https://www.blender.org/download/) if you don't have it. Any
4.x build works (the COLLADA importer is included).

## Features

- Add individual `.dae` files or a **whole folder** (recursive).
- Output **next to each `.dae`** or into a chosen folder.
- **Batch** convert with a progress bar and per-file log.
- Exports `.glb` with skins, animations, normals, tangents, texcoords, and
  materials (Y-up).

## Notes

- Each file converts in a fresh, empty Blender scene, so batches don't bleed
  together; failures are logged and skipped (the rest keep going).
- Prefer no Blender at all? [`assimp`](https://github.com/assimp/assimp) can
  convert from the command line (`assimp export in.dae out.glb`), though its
  glTF skin export is less consistent than Blender's.

## License

MIT.
