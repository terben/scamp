#!/usr/bin/env python3
"""
Write SCAMP .ahead files (TAN + PV, degree 3) for a gen_synth_mosaic.py data
set, as a user would have them from a previous instrument calibration.

The .ahead WCS of every exposure keeps the header pointing and position
angle (with their errors, as in practice), but contains an instrument model
(chip layout + distortion):
  --layout-err 0 --dscale-err 0   exact instrument model ("perfect")
  --layout-err P                  chip positions off by P pixels rms (and P/2000 rad rotation)
  --dscale-err F                  distortion amplitude off by the factor (1+F)

Usage: make_ahead.py DATADIR OUTDIR [--layout-err P] [--dscale-err F] [--seed N]
Writes OUTDIR/exp?.ahead and prints the accuracy of the .ahead WCS.
"""
import sys, os, argparse
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mosaic_lib import *

ap = argparse.ArgumentParser()
ap.add_argument("datadir")
ap.add_argument("outdir")
ap.add_argument("--layout-err", type=float, default=0.0)
ap.add_argument("--dscale-err", type=float, default=0.0)
ap.add_argument("--seed", type=int, default=123)
args = ap.parse_args()
os.makedirs(args.outdir, exist_ok=True)
rng = np.random.default_rng(args.seed)

t = np.load(os.path.join(args.datadir, "truth.npz"))
lay = t["layout"].copy()
nchip = len(lay)
lay_model = lay.copy()
lay_model[:, :2] += rng.normal(0, args.layout_err, (nchip, 2))
lay_model[:, 2] += rng.normal(0, args.layout_err / 2000.0, nchip) / D2R

# polynomial terms (TPV order for degree 3, without the radial terms 3 and 11)
TERMS = [(0, 0, 0), (1, 1, 0), (2, 0, 1), (4, 2, 0), (5, 1, 1), (6, 0, 2),
         (7, 3, 0), (8, 2, 1), (9, 1, 2), (10, 0, 3)]

gx, gy = np.meshgrid(np.linspace(1, NAXIS1, 24), np.linspace(1, NAXIS2, 48))
gx, gy = gx.ravel(), gy.ravel()
worst_fit, worst_truth = 0.0, 0.0
for e in range(len(t["expo"])):
    ims = read_imheads(os.path.join(args.datadir, "exp%d.cat" % (e + 1)))
    ex = expo_from_truth(t["expo"][e])
    h0 = ims[0]
    ra_h, dec_h = h0["CRVAL1"], h0["CRVAL2"]
    pa_h = np.arctan2(-h0["CD2_1"], -h0["CD1_1"]) / D2R      # chip 1 has angle 0
    model = dict(ra0=ra_h, dec0=dec_h, pa=pa_h,
                 k3=ex["k3"] * (1 + args.dscale_err), qs=ex["qs"] * (1 + args.dscale_err))
    blocks = []
    for c in range(nchip):
        h = ims[c]
        cd = np.array([[h["CD1_1"], h["CD1_2"]], [h["CD2_1"], h["CD2_2"]]])
        crpix = np.array([h["CRPIX1"], h["CRPIX2"]])
        ra, dec = pix2sky(gx, gy, lay_model[c], model)
        xi, eta = sky2tan(ra, dec, ra_h, dec_h)
        x = cd[0, 0] * (gx - crpix[0]) + cd[0, 1] * (gy - crpix[1])
        y = cd[1, 0] * (gx - crpix[0]) + cd[1, 1] * (gy - crpix[1])
        # PV1: xi = sum a * x^i y^j ; PV2: eta = sum b * y^i x^j (TPV convention)
        A1 = np.array([x ** i * y ** j for _, i, j in TERMS]).T
        A2 = np.array([y ** i * x ** j for _, i, j in TERMS]).T
        a = np.linalg.lstsq(A1, xi, rcond=None)[0]
        b = np.linalg.lstsq(A2, eta, rcond=None)[0]
        cards = [card("EXTNAME", "CCD_%02d" % (c + 1)),
                 card("CTYPE1", "RA---TAN"), card("CTYPE2", "DEC--TAN"),
                 card("CRVAL1", ra_h), card("CRVAL2", dec_h),
                 card("CRPIX1", crpix[0]), card("CRPIX2", crpix[1]),
                 card("CD1_1", cd[0, 0]), card("CD1_2", cd[0, 1]),
                 card("CD2_1", cd[1, 0]), card("CD2_2", cd[1, 1])]
        cards += [card("PV1_%d" % k, float(v)) for (k, _, _), v in zip(TERMS, a)]
        cards += [card("PV2_%d" % k, float(v)) for (k, _, _), v in zip(TERMS, b)]
        blocks.append("\n".join(cards) + "\n" + "END".ljust(80) + "\n")
        # accuracy of the written WCS: vs. the model it represents, and vs. the truth
        from astropy.io import fits as _f
        w = scamp_wcs(h, _f.Header.fromstring("\n".join(cards) + "\n", sep="\n"))
        rw, dw = w.all_pix2world(gx, gy, 1)
        worst_fit = max(worst_fit, sep_mas(rw, dw, ra, dec).max())
        worst_truth = max(worst_truth, sep_mas(rw, dw, *pix2sky(gx, gy, lay[c], ex)).max())
    open(os.path.join(args.outdir, "exp%d.ahead" % (e + 1)), "w").write("".join(blocks))
print("%s: .ahead written (layout error %.2f px, distortion error %.1f%%); "
      "max fit residual %.4f mas, max error vs. truth %.0f mas"
      % (args.outdir, args.layout_err, 100 * args.dscale_err, worst_fit, worst_truth))
