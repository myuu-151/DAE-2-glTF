#!/usr/bin/env python3
# DAE-2-glTF — a small GUI to convert COLLADA (.dae) files to glTF binary (.glb).
#
# Drop in .dae files, click Convert, get .glb out. Skinning and animation are
# preserved (rigged models stay rigged).
#
# Run:  python dae2gltf.py      (or double-click on Windows)
#
# Under the hood it drives a Blender install in headless mode to do the actual
# COLLADA->glTF work, because re-implementing skinned-COLLADA parsing from
# scratch is huge and fragile while Blender already does it well. The GUI
# auto-detects Blender; if it can't, point it at blender.exe with "Browse".

import os
import sys
import glob
import shutil
import tempfile
import threading
import subprocess

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

APP_TITLE = "DAE-2-glTF"

# Headless Blender script: empty scene -> import .dae -> export .glb (rig kept).
_BLENDER_SCRIPT = r'''
import bpy, sys, os
argv = sys.argv[sys.argv.index("--") + 1:]
src, dst = argv[0], argv[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
if not hasattr(bpy.ops.wm, "collada_import"):
    print("DAE2GLTF_ERR: this Blender build has no COLLADA importer")
    sys.exit(2)
bpy.ops.wm.collada_import(filepath=src)
os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
bpy.ops.export_scene.gltf(
    filepath=dst, export_format="GLB",
    export_skins=True, export_animations=True, export_yup=True,
    export_apply=False, export_tangents=True, export_normals=True,
    export_texcoords=True, export_materials="EXPORT")
print("DAE2GLTF_OK")
'''


def find_blender():
    """Best-effort locate a Blender executable."""
    p = shutil.which("blender")
    if p:
        return p
    pats = [
        r"C:\Program Files\Blender Foundation\Blender*\blender.exe",
        r"C:\Program Files (x86)\Blender Foundation\Blender*\blender.exe",
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/usr/bin/blender", "/usr/local/bin/blender",
        os.path.expanduser("~/Applications/Blender.app/Contents/MacOS/Blender"),
    ]
    hits = []
    for pat in pats:
        hits += glob.glob(pat)
    # Prefer the highest-versioned match.
    hits.sort(reverse=True)
    return hits[0] if hits else ""


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("640x520")
        root.minsize(520, 440)

        self.blender = tk.StringVar(value=find_blender())
        self.same_dir = tk.BooleanVar(value=True)
        self.out_dir = tk.StringVar(value="")
        self.files = []   # input .dae paths

        pad = {"padx": 8, "pady": 4}

        # --- Blender path row ---
        bf = ttk.LabelFrame(root, text="Blender (conversion engine)")
        bf.pack(fill="x", **pad)
        ttk.Entry(bf, textvariable=self.blender).pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Button(bf, text="Browse…", command=self.pick_blender).pack(side="left", padx=6)

        # --- Input files ---
        inf = ttk.LabelFrame(root, text="Input .dae files")
        inf.pack(fill="both", expand=True, **pad)
        self.listbox = tk.Listbox(inf, selectmode="extended")
        self.listbox.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        sb = ttk.Scrollbar(inf, command=self.listbox.yview)
        sb.pack(side="left", fill="y")
        self.listbox.config(yscrollcommand=sb.set)
        btns = ttk.Frame(inf)
        btns.pack(side="left", fill="y", padx=6)
        ttk.Button(btns, text="Add files…", command=self.add_files).pack(fill="x", pady=2)
        ttk.Button(btns, text="Add folder…", command=self.add_folder).pack(fill="x", pady=2)
        ttk.Button(btns, text="Remove", command=self.remove_sel).pack(fill="x", pady=2)
        ttk.Button(btns, text="Clear", command=self.clear).pack(fill="x", pady=2)

        # --- Output ---
        of = ttk.LabelFrame(root, text="Output")
        of.pack(fill="x", **pad)
        ttk.Checkbutton(of, text="Write .glb next to each .dae",
                        variable=self.same_dir, command=self._toggle_out).pack(anchor="w", padx=6, pady=2)
        orow = ttk.Frame(of)
        orow.pack(fill="x", padx=6, pady=2)
        self.out_entry = ttk.Entry(orow, textvariable=self.out_dir, state="disabled")
        self.out_entry.pack(side="left", fill="x", expand=True)
        self.out_btn = ttk.Button(orow, text="Folder…", command=self.pick_out, state="disabled")
        self.out_btn.pack(side="left", padx=6)

        # --- Convert + log ---
        cf = ttk.Frame(root)
        cf.pack(fill="x", **pad)
        self.convert_btn = ttk.Button(cf, text="Convert", command=self.start)
        self.convert_btn.pack(side="left")
        self.progress = ttk.Progressbar(cf, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        self.log = scrolledtext.ScrolledText(root, height=8, state="disabled")
        self.log.pack(fill="both", expand=False, **pad)

        if not self.blender.get():
            self._log("Blender not found automatically — set its path above.")

    # ---- UI helpers ----
    def _toggle_out(self):
        state = "disabled" if self.same_dir.get() else "normal"
        self.out_entry.config(state=state)
        self.out_btn.config(state=state)

    def pick_blender(self):
        f = filedialog.askopenfilename(title="Locate Blender",
                                       filetypes=[("Blender", "blender.exe blender Blender"), ("All", "*.*")])
        if f:
            self.blender.set(f)

    def add_files(self):
        fs = filedialog.askopenfilenames(title="Add .dae files",
                                         filetypes=[("COLLADA", "*.dae"), ("All", "*.*")])
        for f in fs:
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", f)

    def add_folder(self):
        d = filedialog.askdirectory(title="Add a folder of .dae files")
        if not d:
            return
        for f in sorted(glob.glob(os.path.join(d, "**", "*.dae"), recursive=True)):
            if f not in self.files:
                self.files.append(f)
                self.listbox.insert("end", f)

    def remove_sel(self):
        for i in reversed(self.listbox.curselection()):
            del self.files[i]
            self.listbox.delete(i)

    def clear(self):
        self.files.clear()
        self.listbox.delete(0, "end")

    def pick_out(self):
        d = filedialog.askdirectory(title="Output folder")
        if d:
            self.out_dir.set(d)

    def _log(self, msg):
        self.log.config(state="normal")
        self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    # ---- Conversion ----
    def start(self):
        blender = self.blender.get().strip()
        if not blender or not os.path.exists(blender):
            messagebox.showerror(APP_TITLE, "Set a valid Blender executable path first.")
            return
        if not self.files:
            messagebox.showerror(APP_TITLE, "Add at least one .dae file.")
            return
        if not self.same_dir.get() and not self.out_dir.get().strip():
            messagebox.showerror(APP_TITLE, "Pick an output folder (or tick 'next to each .dae').")
            return
        self.convert_btn.config(state="disabled")
        threading.Thread(target=self._run, args=(blender, list(self.files)), daemon=True).start()

    def _out_path(self, src):
        name = os.path.splitext(os.path.basename(src))[0] + ".glb"
        if self.same_dir.get():
            return os.path.join(os.path.dirname(src), name)
        return os.path.join(self.out_dir.get().strip(), name)

    def _run(self, blender, files):
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(_BLENDER_SCRIPT)
            script = tf.name
        self.progress.config(maximum=len(files), value=0)
        ok = 0
        try:
            for i, src in enumerate(files, 1):
                dst = self._out_path(src)
                self._log("[%d/%d] %s" % (i, len(files), os.path.basename(src)))
                try:
                    proc = subprocess.run(
                        [blender, "--background", "--python", script, "--", src, dst],
                        capture_output=True, text=True, timeout=600)
                    out = (proc.stdout or "") + (proc.stderr or "")
                    if "DAE2GLTF_OK" in out and os.path.exists(dst):
                        self._log("    -> %s" % dst)
                        ok += 1
                    else:
                        tail = out.strip().splitlines()[-1] if out.strip() else "no output"
                        self._log("    FAILED: %s" % tail)
                except Exception as e:
                    self._log("    FAILED: %s" % e)
                self.progress.config(value=i)
        finally:
            try:
                os.remove(script)
            except OSError:
                pass
        self._log("Done: %d/%d converted." % (ok, len(files)))
        self.convert_btn.config(state="normal")


def main():
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
