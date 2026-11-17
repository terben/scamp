#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic multichip test of the two-stage workflow for a camera whose chip
layout in the image headers is wrong (by ~50 pixels and 0.1 deg per chip):

 1. calibration data set A (no .ahead): MOSAIC_TYPE LOOSE with
    STABILITY_TYPE EXPOSURE recovers every chip;
 2. the .head of one exposure of A becomes the instrument model (.ahead,
    without CRVAL, head2ahead.py) for a science data set B taken with the
    same camera elsewhere on the sky; B is solved with FIX_FOCALPLANE and
    UNCHANGED (STABILITY_TYPE INSTRUMENT).

All solutions are compared with the ground truth (check_mosaic.py). Also
checks that MOSAIC_TYPE LOOSE with STABILITY_TYPE INSTRUMENT is refused.
"""
import os, subprocess, sys

srcdir = os.environ.get("srcdir", ".")
scamp = os.path.abspath(os.path.join("..", "src", "scamp"))
outdir = "test_mosaic02.d"
dirA, dirB = os.path.join(outdir, "A"), os.path.join(outdir, "B")
camera = ["--layout-off", "50", "--layout-rot", "0.1", "--camera-seed", "7",
          "--nstar", "20000"]
cats = ["exp%d.cat" % i for i in range(1, 7)]

def run(cmd, **kw):
  print("+", " ".join(cmd))
  sys.stdout.flush()
  return subprocess.call(cmd, **kw)

def scamp_run(d, opts, quiet=False):
  return run([scamp] + cats + ["-c", os.path.abspath(os.path.join(outdir, "default.scamp")),
    "-ASTREF_CATALOG", "FILE", "-ASTREFCAT_NAME", "ref.cat",
    "-ASTREFCENT_KEYS", "X_WORLD,Y_WORLD",
    "-ASTREFERR_KEYS", "ERRA_WORLD,ERRB_WORLD,ERRTHETA_WORLD",
    "-ASTREFMAG_KEY", "MAG", "-ASTREFMAGERR_KEY", "MAGERR",
    "-ASTREFOBSDATE_KEY", "OBSDATE",
    "-ASTRINSTRU_KEY", "FILTER", "-PHOTINSTRU_KEY", "FILTER",
    "-AHEADER_SUFFIX", ".ahead", "-CHECKPLOT_TYPE", "NONE",
    "-VERBOSE_TYPE", "QUIET" if quiet else "NORMAL"] + opts, cwd=d)

def check(d, max_rms, max_grid):
  return run([sys.executable, os.path.join(srcdir, "check_mosaic.py"), d,
              "--max-rms", str(max_rms), "--max-grid", str(max_grid)]) == 0

# Data sets: same camera, different fields, pointings and header errors
if run([sys.executable, os.path.join(srcdir, "gen_synth_mosaic.py"), dirA] + camera) \
   or run([sys.executable, os.path.join(srcdir, "gen_synth_mosaic.py"), dirB] + camera
          + ["--seed", "2", "--ra0", "210.3", "--dec0", "-12.5"]):
  print("Data generation ... failed")
  sys.exit(1)
with open(os.path.join(outdir, "default.scamp"), "w") as f:
  if subprocess.call([scamp, "-dd"], stdout=f) != 0:
    print("SCAMP default configuration ... failed")
    sys.exit(1)

ok = True

# LOOSE with the default STABILITY_TYPE INSTRUMENT must be refused
ret = scamp_run(dirA, ["-MOSAIC_TYPE", "LOOSE", "-XML_NAME", "refused.xml"], quiet=True)
print("MOSAIC_TYPE LOOSE + STABILITY_TYPE INSTRUMENT refused ... %s"
      % ("passed" if ret != 0 else "FAILED"))
ok &= ret != 0

# Stage 1: calibration set, LOOSE + EXPOSURE
if scamp_run(dirA, ["-MOSAIC_TYPE", "LOOSE", "-STABILITY_TYPE", "EXPOSURE",
                    "-XML_NAME", "stage1.xml"]) != 0:
  print("SCAMP execution (stage 1) ... failed")
  sys.exit(1)
print("Stage 1 (A, LOOSE + EXPOSURE):")
ok &= check(dirA, 15.0, 150.0)

# Instrument model from exposure 1 of A
if run([sys.executable, os.path.join(srcdir, "head2ahead.py"),
        os.path.join(dirA, "exp1.head"), dirB] + ["exp%d" % i for i in range(1, 7)]):
  print("Instrument model ... failed")
  sys.exit(1)

# Stage 2: science set with the instrument model
for mosaic in ("FIX_FOCALPLANE", "UNCHANGED"):
  if scamp_run(dirB, ["-MOSAIC_TYPE", mosaic, "-STABILITY_TYPE", "INSTRUMENT",
                      "-XML_NAME", "stage2_%s.xml" % mosaic]) != 0:
    print("SCAMP execution (stage 2, %s) ... failed" % mosaic)
    ok = False
    continue
  print("Stage 2 (B, model from A, MOSAIC_TYPE %s):" % mosaic)
  ok &= check(dirB, 5.0, 40.0)

sys.exit(0 if ok else 1)
