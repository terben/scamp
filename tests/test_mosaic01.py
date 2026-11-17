#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic multichip test: an OmegaCAM-like 8x4-CCD camera (gen_synth_mosaic.py)
with .ahead instrument models (make_ahead.py) whose distortion polynomials
have non-zero constant terms (PV1_0/PV2_0), as in SCAMP's own output.

The solutions for MOSAIC_TYPE UNCHANGED and FIX_FOCALPLANE are compared with
the ground truth (check_mosaic.py). Before the fix in crval_to_crpix(), the
constant PV terms were applied twice with FIX_FOCALPLANE (errors of several
arcseconds).
"""
import os, subprocess, sys

srcdir = os.environ.get("srcdir", ".")
scamp = os.path.abspath(os.path.join("..", "src", "scamp"))
outdir = "test_mosaic01.d"
MAX_RMS, MAX_GRID = 5.0, 40.0          # mas

def run(cmd, **kw):
  print("+", " ".join(cmd))
  sys.stdout.flush()
  return subprocess.call(cmd, **kw)

# Generate the data set and the .ahead files (next to the catalogs)
if run([sys.executable, os.path.join(srcdir, "gen_synth_mosaic.py"), outdir,
        "--nstar", "20000"]) != 0 \
   or run([sys.executable, os.path.join(srcdir, "make_ahead.py"), outdir, outdir]) != 0:
  print("Data generation ... failed")
  sys.exit(1)

with open(os.path.join(outdir, "default.scamp"), "w") as f:
  if subprocess.call([scamp, "-dd"], stdout=f) != 0:
    print("SCAMP default configuration ... failed")
    sys.exit(1)

cats = ["exp%d.cat" % i for i in range(1, 7)]
status = 0
for mosaic in ("UNCHANGED", "FIX_FOCALPLANE"):
  ret = run([scamp] + cats + ["-c", "default.scamp",
    "-ASTREF_CATALOG", "FILE", "-ASTREFCAT_NAME", "ref.cat",
    "-ASTREFCENT_KEYS", "X_WORLD,Y_WORLD",
    "-ASTREFERR_KEYS", "ERRA_WORLD,ERRB_WORLD,ERRTHETA_WORLD",
    "-ASTREFMAG_KEY", "MAG", "-ASTREFMAGERR_KEY", "MAGERR",
    "-ASTREFOBSDATE_KEY", "OBSDATE",
    "-ASTRINSTRU_KEY", "FILTER", "-PHOTINSTRU_KEY", "FILTER",
    "-MOSAIC_TYPE", mosaic, "-AHEADER_SUFFIX", ".ahead",
    "-CHECKPLOT_TYPE", "NONE", "-XML_NAME", "mosaic_%s.xml" % mosaic,
    "-VERBOSE_TYPE", "NORMAL"], cwd=outdir)
  if ret != 0:
    print("SCAMP execution (MOSAIC_TYPE %s) ... failed" % mosaic)
    status = 1
    continue
  print("MOSAIC_TYPE %s:" % mosaic)
  if run([sys.executable, os.path.join(srcdir, "check_mosaic.py"), outdir,
          "--max-rms", str(MAX_RMS), "--max-grid", str(MAX_GRID)]) != 0:
    status = 1

sys.exit(status)
