#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic end-to-end test: generate catalogues with a known astrometric
and photometric ground truth (gen_synth.py), run SCAMP on them and check
the recovered solution against the truth (check_synth.py).
"""
import os, subprocess, sys

srcdir = os.environ.get("srcdir", ".")
scamp = os.path.abspath(os.path.join("..", "src", "scamp"))
outdir = "test_synthetic01.d"

def run(cmd, **kw):
  print("+", " ".join(cmd))
  sys.stdout.flush()
  return subprocess.call(cmd, **kw)

# Generate data set
if run([sys.executable, os.path.join(srcdir, "gen_synth.py"), outdir]) != 0:
  print("Data generation ... failed")
  sys.exit(1)

# Run SCAMP (default configuration + overrides)
with open(os.path.join(outdir, "default.scamp"), "w") as f:
  if subprocess.call([scamp, "-dd"], stdout=f) != 0:
    print("SCAMP default configuration ... failed")
    sys.exit(1)

cats = ["exp%d.cat" % i for i in range(1, 6)]
ret = run([scamp] + cats + ["-c", "default.scamp",
  "-ASTREF_CATALOG", "FILE", "-ASTREFCAT_NAME", "ref.cat",
  "-ASTREFCENT_KEYS", "X_WORLD,Y_WORLD",
  "-ASTREFERR_KEYS", "ERRA_WORLD,ERRB_WORLD,ERRTHETA_WORLD",
  "-ASTREFMAG_KEY", "MAG", "-ASTREFMAGERR_KEY", "MAGERR",
  "-ASTREFOBSDATE_KEY", "OBSDATE",
  "-ASTRINSTRU_KEY", "FILTER", "-PHOTINSTRU_KEY", "FILTER",
  "-DISTORT_DEGREES", "3",
  "-CHECKPLOT_TYPE", "NONE", "-XML_NAME", "synth.xml",
  "-VERBOSE_TYPE", "NORMAL"], cwd=outdir)
print("%-24s ... %s" % ("SCAMP execution", "passed" if ret == 0 else "failed"))
if ret != 0:
  sys.exit(1)

# Compare with ground truth
sys.exit(run([sys.executable, os.path.join(srcdir, "check_synth.py"), outdir]))
