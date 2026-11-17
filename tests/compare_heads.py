#!/usr/bin/env python3
"""Compare two sets of SCAMP .head solutions for the same LDAC catalogs.
usage: compare_heads.py dirA dirB cat1 [cat2 ...]
For every extension, evaluate both WCS solutions on a pixel grid and report
the max/rms sky separation (mas)."""
import sys, os, warnings
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS, FITSFixedWarning
from astropy.utils.exceptions import AstropyWarning
warnings.simplefilter("ignore", FITSFixedWarning)
warnings.simplefilter("ignore", AstropyWarning)
D2R = np.pi / 180

def imheads(cat):
    out = []
    for h in fits.open(cat):
        if h.name != "LDAC_IMHEAD":
            continue
        c = h.data[0][0]
        if not isinstance(c, str):
            c = "".join(s.ljust(80) for s in c)
        out.append(fits.Header.fromstring(c.rstrip("\x00")))
    return out

def heads(fn):
    txt = open(fn).read()
    blocks = [b for b in txt.split("\nEND") if "CRVAL1" in b]
    return [fits.Header.fromstring(b.strip("\n") + "\n", sep="\n") for b in blocks]

def mkwcs(h0, hs):
    h = h0.copy()
    for k in list(h.keys()):
        if k.startswith(("PV", "CD", "PC", "CDELT", "CROTA")):
            h.remove(k, ignore_missing=True, remove_all=True)
    h.update(hs)
    if any(k.startswith("PV") for k in hs.keys()):
        h["CTYPE1"], h["CTYPE2"] = "RA---TPV", "DEC--TPV"
    return WCS(h)

dA, dB, cats = sys.argv[1], sys.argv[2], sys.argv[3:]
gmax = 0.0
for cat in cats:
    base = os.path.splitext(os.path.basename(cat))[0] + ".head"
    ims = imheads(cat)
    hA, hB = heads(os.path.join(dA, base)), heads(os.path.join(dB, base))
    assert len(ims) == len(hA) == len(hB), (cat, len(ims), len(hA), len(hB))
    mx = []
    for h0, a, b in zip(ims, hA, hB):
        nx, ny = h0["NAXIS1"], h0["NAXIS2"]
        x, y = np.meshgrid(np.linspace(1, nx, 21), np.linspace(1, ny, 41))
        ra1, de1 = mkwcs(h0, a).all_pix2world(x, y, 1)
        ra2, de2 = mkwcs(h0, b).all_pix2world(x, y, 1)
        d = np.hypot((ra1 - ra2) * np.cos(de2 * D2R), de1 - de2) * 3.6e6
        mx.append(d.max())
    fs = [(a.get("FLXSCALE"), b.get("FLXSCALE")) for a, b in zip(hA, hB)]
    dfs = max(abs(2.5 * np.log10(p / q)) for p, q in fs if p and q) if fs[0][0] else 0
    print("%-28s next=%2d  max dpos = %9.4f mas  (median chip %8.4f)  max dmag(FLXSCALE)=%.2e"
          % (os.path.basename(cat), len(ims), max(mx), np.median(mx), dfs))
    gmax = max(gmax, max(mx))
print("OVERALL max dpos = %.4f mas" % gmax)
