#!/usr/bin/env python3
# DAE-2-glTF — a small standalone GUI to convert COLLADA (.dae) to glTF (.glb).
#
# Add .dae files, click Convert, get .glb out. Skinning and animation are
# preserved (rigged models stay rigged).
#
# Self-contained: the conversion is done in-process through the bundled
# Open Asset Import Library (assimp) via its C API — no Blender, no external
# tools. assimp is BSD-3-Clause (see THIRDPARTY/assimp-LICENSE).
#
# Run:  python dae2gltf.py     (or run the packaged .exe)

import os
import re
import sys
import glob
import ctypes
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

APP_TITLE = "DAE-2-glTF"

# assimp post-process: triangulate (glTF only allows triangles) + drop degenerate
# tris. Keep it minimal so the model stays faithful (we don't regenerate normals).
_AI_PROCESS = 0x8 | 0x100000  # aiProcess_Triangulate | aiProcess_FindDegenerates


def _dll_candidates():
    names = ["assimp-vc143-mt.dll", "assimp.dll", "libassimp.so", "libassimp.dylib"]
    bases = []
    if hasattr(sys, "_MEIPASS"):                       # PyInstaller bundle
        bases.append(sys._MEIPASS)
    try:
        bases.append(os.path.dirname(os.path.abspath(__file__)))
    except NameError:
        pass
    bases.append(os.path.dirname(os.path.abspath(sys.argv[0])) if sys.argv and sys.argv[0] else "")
    bases.append(os.getcwd())
    for b in bases:
        for n in names:
            p = os.path.join(b, n)
            if os.path.exists(p):
                yield p


_ID_ATTR = re.compile(rb'\bid="([^"]+)"')
_REF_ATTR = re.compile(rb'\b(source|url)="([^"#][^"]*)"')
_SKEL_TEXT = re.compile(rb'(<skeleton>)([^<#][^<]*)(</skeleton>)')


def sanitize_dae(src):
    """Fix bare local references some exporters write (source="Foo-array"
    instead of source="#Foo-array") — assimp rejects them with "Unknown
    reference format in url". Only values that match an id actually defined
    in the document get the '#' prepended, so external URIs are untouched.
    Returns (path_to_use, fix_count); writes a temp .dae NEXT TO the source
    (relative texture paths must keep resolving) when fixes were needed."""
    with open(src, "rb") as f:
        data = f.read()
    ids = set(_ID_ATTR.findall(data))
    fixes = [0]

    def fix_attr(m):
        if m.group(2) in ids:
            fixes[0] += 1
            return m.group(1) + b'="#' + m.group(2) + b'"'
        return m.group(0)

    def fix_skel(m):
        if m.group(2).strip() in ids:
            fixes[0] += 1
            return m.group(1) + b'#' + m.group(2) + m.group(3)
        return m.group(0)

    data = _REF_ATTR.sub(fix_attr, data)
    data = _SKEL_TEXT.sub(fix_skel, data)
    if not fixes[0]:
        return src, 0
    tmp = os.path.join(os.path.dirname(os.path.abspath(src)),
                       "." + os.path.basename(src) + ".d2g_tmp.dae")
    with open(tmp, "wb") as f:
        f.write(data)
    return tmp, fixes[0]


class Assimp:
    """Thin ctypes wrapper over assimp's C import/export API."""

    def __init__(self):
        self.path = next(_dll_candidates(), "")
        if not self.path:
            raise FileNotFoundError("assimp library not found next to the app")
        d = ctypes.CDLL(self.path)
        d.aiImportFile.restype = ctypes.c_void_p
        d.aiImportFile.argtypes = [ctypes.c_char_p, ctypes.c_uint]
        d.aiExportScene.restype = ctypes.c_int
        d.aiExportScene.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        d.aiReleaseImport.argtypes = [ctypes.c_void_p]
        d.aiGetErrorString.restype = ctypes.c_char_p
        self.d = d

    def _err(self):
        msg = self.d.aiGetErrorString()
        return msg.decode("utf-8", "replace") if msg else ""

    def convert(self, src, dst):
        scene = self.d.aiImportFile(src.encode("utf-8"), _AI_PROCESS)
        if not scene:
            raise RuntimeError(self._err() or "import failed")
        try:
            d = os.path.dirname(os.path.abspath(dst))
            if d:
                os.makedirs(d, exist_ok=True)
            fmt = b"glb2" if dst.lower().endswith(".glb") else b"gltf2"
            ret = self.d.aiExportScene(scene, fmt, dst.encode("utf-8"), 0)
            if ret != 0:
                raise RuntimeError(self._err() or ("export failed (code %d)" % ret))
        finally:
            self.d.aiReleaseImport(scene)


class App:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        root.geometry("620x500")
        root.minsize(500, 420)

        try:
            self.engine = Assimp()
            self.engine_err = ""
        except Exception as e:
            self.engine = None
            self.engine_err = str(e)

        self.same_dir = tk.BooleanVar(value=True)
        self.out_dir = tk.StringVar(value="")
        self.files = []
        pad = {"padx": 8, "pady": 4}

        # Engine status
        ef = ttk.Frame(root)
        ef.pack(fill="x", **pad)
        if self.engine:
            ttk.Label(ef, text="Engine: assimp (bundled) — no Blender needed").pack(side="left")
        else:
            ttk.Label(ef, text="assimp library missing — see THIRDPARTY/assimp-LICENSE",
                      foreground="red").pack(side="left")

        # Input files
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

        # Output
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

        # Convert + log
        cf = ttk.Frame(root)
        cf.pack(fill="x", **pad)
        self.convert_btn = ttk.Button(cf, text="Convert", command=self.start)
        self.convert_btn.pack(side="left")
        if not self.engine:
            self.convert_btn.config(state="disabled")
        self.progress = ttk.Progressbar(cf, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=8)

        self.log = scrolledtext.ScrolledText(root, height=8, state="disabled")
        self.log.pack(fill="both", expand=False, **pad)
        if self.engine_err:
            self._log("Error: " + self.engine_err)

    def _toggle_out(self):
        state = "disabled" if self.same_dir.get() else "normal"
        self.out_entry.config(state=state)
        self.out_btn.config(state=state)

    def add_files(self):
        for f in filedialog.askopenfilenames(title="Add .dae files",
                                             filetypes=[("COLLADA", "*.dae"), ("All", "*.*")]):
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

    def start(self):
        if not self.engine:
            return
        if not self.files:
            messagebox.showerror(APP_TITLE, "Add at least one .dae file.")
            return
        if not self.same_dir.get() and not self.out_dir.get().strip():
            messagebox.showerror(APP_TITLE, "Pick an output folder (or tick 'next to each .dae').")
            return
        self.convert_btn.config(state="disabled")
        threading.Thread(target=self._run, args=(list(self.files),), daemon=True).start()

    def _out_path(self, src):
        name = os.path.splitext(os.path.basename(src))[0] + ".glb"
        if self.same_dir.get():
            return os.path.join(os.path.dirname(src), name)
        return os.path.join(self.out_dir.get().strip(), name)

    def _run(self, files):
        self.progress.config(maximum=len(files), value=0)
        ok = 0
        for i, src in enumerate(files, 1):
            dst = self._out_path(src)
            self._log("[%d/%d] %s" % (i, len(files), os.path.basename(src)))
            tmp = None
            try:
                use, nfix = sanitize_dae(src)
                if nfix:
                    tmp = use
                    self._log("    fixed %d bare reference(s) (missing '#')" % nfix)
                self.engine.convert(use, dst)
                self._log("    -> %s" % dst)
                ok += 1
            except Exception as e:
                self._log("    FAILED: %s" % e)
            finally:
                if tmp:
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
            self.progress.config(value=i)
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
