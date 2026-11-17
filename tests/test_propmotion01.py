#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Synthetic proper motion test: generate multi-epoch catalogues of moving
stars (gen_synth_pm.py), run SCAMP with COMPUTE_PROPERMOTIONS, with and
without the reference catalogue in the proper motion fit
(INCLUDE_ASTREFCATALOG Y/N), and compare the measured proper motions of
the merged sources with the truth.
"""
import os, subprocess, sys, warnings
import numpy as np

srcdir = os.environ.get("srcdir", ".")
scamp = os.path.abspath(os.path.join("..", "src", "scamp"))
outdir = "test_propmotion01.d"
D2R = np.pi / 180

# Limits (mas/yr). With these data SCAMP reaches a robust scatter of about
# 3-4 mas/yr, dominated by a field-wide linear drift of the per-exposure
# solutions; slopes for fast movers are within 1% of unity.
MAX_ZERO_FRAC = 0.01
MAX_MAD = 6.0
SLOPE_TOL = 0.05

def run(cmd, **kw):
  print("+", " ".join(cmd))
  sys.stdout.flush()
  return subprocess.call(cmd, **kw)

def report(name, passed):
  print("%-48s ... %s" % (name, "passed" if passed else "failed"))
  return passed

def match(ra, dec, ra_t, dec_t, rad):
  """Index of the nearest true star within rad (deg), or -1."""
  cosd = np.cos(np.median(dec_t) * D2R)
  kx = lambda r: np.floor(r * cosd / rad).astype(int)
  ky = lambda d: np.floor(d / rad).astype(int)
  grid = {}
  for i, key in enumerate(zip(kx(ra_t), ky(dec_t))):
    grid.setdefault(key, []).append(i)
  out = np.full(len(ra), -1)
  for j, (a, b) in enumerate(zip(kx(ra), ky(dec))):
    best, bd = -1, rad * rad
    for da in (-1, 0, 1):
      for db in (-1, 0, 1):
        for i in grid.get((a + da, b + db), ()):
          dd = ((ra[j] - ra_t[i]) * cosd) ** 2 + (dec[j] - dec_t[i]) ** 2
          if dd < bd:
            best, bd = i, dd
    out[j] = best
  return out

def mad(x):
  return 1.4826 * np.median(np.abs(x - np.median(x)))

# Generate data set
if run([sys.executable, os.path.join(srcdir, "gen_synth_pm.py"), outdir]) != 0:
  print("Data generation ... failed")
  sys.exit(1)

with open(os.path.join(outdir, "default.scamp"), "w") as f:
  if subprocess.call([scamp, "-dd"], stdout=f) != 0:
    print("SCAMP default configuration ... failed")
    sys.exit(1)

from astropy.io import fits
truth = np.load(os.path.join(outdir, "truth.npz"))
cats = ["exp%d.cat" % i for i in range(1, len(truth["epochs"]) + 1)]
fast_t = (np.abs(truth["pmra"]) > 15) | (np.abs(truth["pmde"]) > 15)
ok = True

for inc in ("Y", "N"):
  tag = "inc" + inc
  ret = run([scamp] + cats + ["-c", "default.scamp",
    "-ASTREF_CATALOG", "FILE", "-ASTREFCAT_NAME", "ref.cat",
    "-ASTREFCENT_KEYS", "X_WORLD,Y_WORLD",
    "-ASTREFERR_KEYS", "ERRA_WORLD,ERRB_WORLD,ERRTHETA_WORLD",
    "-ASTREFMAG_KEY", "MAG", "-ASTREFMAGERR_KEY", "MAGERR",
    "-ASTREFOBSDATE_KEY", "OBSDATE",
    "-ASTREFPROP_KEYS", "PMALPHA_J2000,PMDELTA_J2000",
    "-ASTREFPROPERR_KEYS", "PMALPHAERR_J2000,PMDELTAERR_J2000",
    "-ASTRINSTRU_KEY", "FILTER", "-PHOTINSTRU_KEY", "FILTER",
    "-DISTORT_DEGREES", "3", "-CHECKPLOT_TYPE", "NONE",
    "-COMPUTE_PROPERMOTIONS", "Y", "-INCLUDE_ASTREFCATALOG", inc,
    "-MERGEDOUTCAT_TYPE", "FITS_LDAC", "-MERGEDOUTCAT_NAME", tag + ".cat",
    "-XML_NAME", tag + ".xml", "-VERBOSE_TYPE", "NORMAL"], cwd=outdir)
  if not report("SCAMP execution (INCLUDE_ASTREFCATALOG %s)" % inc, ret == 0):
    ok = False
    continue

  with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    m = fits.open(os.path.join(outdir, tag + "_1.cat"))[2].data
  i = match(m["ALPHA_J2000"], m["DELTA_J2000"], truth["ra"], truth["dec"], 2.0 / 3600)
  good = (i >= 0) & (m["NPOS_OK"] >= 5)
  i, m = i[good], m[good]
  pma, pmd = m["PMALPHA_J2000"], m["PMDELTA_J2000"]
  print("%d merged sources with >= 5 detections matched to the truth" % len(m))

  zero = np.mean((pma == 0.0) & (pmd == 0.0))
  ok &= report("[%s] sources without proper motion: %.1f%% (< %.0f%%)"
               % (inc, 100 * zero, 100 * MAX_ZERO_FRAC), zero < MAX_ZERO_FRAC)
  for axis, meas, true in (("PMALPHA", pma, truth["pmra"][i]),
                           ("PMDELTA", pmd, truth["pmde"][i])):
    s = mad(meas - true)
    ok &= report("[%s] %s robust scatter: %.2f mas/yr (< %.1f)"
                 % (inc, axis, s, MAX_MAD), s < MAX_MAD)
    f = fast_t[i]
    slope = np.polyfit(true[f], meas[f], 1)[0]
    ok &= report("[%s] %s slope for fast movers: %.3f (1 +/- %.2f)"
                 % (inc, axis, slope, SLOPE_TOL), abs(slope - 1) < SLOPE_TOL)

sys.exit(0 if ok else 1)
