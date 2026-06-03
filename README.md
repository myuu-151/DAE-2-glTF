# DAE-2-glTF

A small **standalone GUI** that converts COLLADA `.dae` files to glTF binary
`.glb` — **no Blender, no dependencies**.

Add your `.dae` files, click **Convert**, get `.glb` out. **Skinning and
animation are preserved**, so rigged models stay rigged.

## Run

**Easiest:** grab `DAE-2-glTF.exe` from [Releases](../../releases) and run it.
Everything is bundled — nothing to install.

**From source:**

```sh
python dae2gltf.py
```

Needs Python 3 with Tkinter (ships with the standard installer on Windows/macOS;
`apt install python3-tk` on Linux) and the `assimp-vc143-mt.dll` that sits next
to `dae2gltf.py` in this repo.

## How it works

The conversion runs **in-process** through the [Open Asset Import Library
(assimp)](https://github.com/assimp/assimp) via its C API (`aiImportFile` →
`aiExportScene "glb2"`). assimp reads COLLADA (geometry, skinning, animation)
and writes glTF 2.0, so the whole thing is one self-contained program — there's
no Blender or command-line tool to find.

## Features

- Add individual `.dae` files or a **whole folder** (recursive).
- Output **next to each `.dae`** or into a chosen folder.
- **Batch** convert with a progress bar and per-file log.
- Meshes are triangulated on export (glTF only allows triangles).

## Notes

- Why assimp and not Blender? Blender 5.0 **removed** COLLADA import, and a
  from-scratch skinned-COLLADA parser is huge and brittle. assimp does it well
  and is tiny to bundle.
- assimp's COLLADA import is solid; its glTF export is good but not perfect on
  exotic rigs — if a clip looks off, the source `.dae` is usually the culprit.

## Third-party

Bundles the assimp library (`assimp-vc143-mt.dll`), BSD-3-Clause — see
[`THIRDPARTY/assimp-LICENSE`](THIRDPARTY/assimp-LICENSE).

## License

MIT (this tool).
