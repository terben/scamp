#!/usr/bin/env python3
"""
Compare SCAMP's .head solutions for a gen_synth_mosaic.py data set with the
ground truth.

For every exposure and chip, the SCAMP WCS (evaluated with wcslib, TPV) is
compared with the TRUE mapping
  (a) at the true pixel positions of the detected stars, and
  (b) on a 17x33 grid covering the whole chip (including corners without stars).
Also checks the relative photometric zero-points (FLXSCALE).

Usage: check_mosaic.py DIR [--max-rms MAS] [--max-grid MAS] [--max-dzp MAG]
                           [--json FILE]
Exit status 0 if all limits are met.
"""
import sys, os, argparse, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mosaic_lib import *

ap = argparse.ArgumentParser()
ap.add_argument("dir")
ap.add_argument("--max-rms", type=float, default=None, help="limit on rms at the stars (mas)")
ap.add_argument("--max-grid", type=float, default=None, help="limit on max on the grid (mas)")
ap.add_argument("--max-dzp", type=float, default=None, help="limit on zero-point error (mag)")
ap.add_argument("--json", default=None)
ap.add_argument("--quiet", action="store_true")
args = ap.parse_args()

t = np.load(os.path.join(args.dir, "truth.npz"))
lay = t["layout"]
nexp = len(t["expo"])
gx, gy = np.meshgrid(np.linspace(0.5, NAXIS1 + 0.5, 17), np.linspace(0.5, NAXIS2 + 0.5, 33))

res = dict(exposures=[])
allstar, allgrid = [], []
fluxscale = []
if not args.quiet:
    print("%-5s %10s %10s %10s %10s   worst chip" % ("Exp", "stars:rms", "stars:max",
                                                    "grid:rms", "grid:max"))
for e in range(nexp):
    expo = expo_from_truth(t["expo"][e])
    ims = read_imheads(os.path.join(args.dir, "exp%d.cat" % (e + 1)))
    hs = read_heads(os.path.join(args.dir, "exp%d.head" % (e + 1)))
    assert len(ims) == len(hs) == len(lay), (len(ims), len(hs), len(lay))
    rstar, rgrid, chipmax = [], [], []
    for c in range(len(lay)):
        w = scamp_wcs(ims[c], hs[c])
        idx = t["idx%d_%d" % (e, c)]
        x, y = t["x%d_%d" % (e, c)], t["y%d_%d" % (e, c)]
        rs = sep_mas(*w.all_pix2world(x, y, 1), t["ra"][idx], t["dec"][idx])
        rg = sep_mas(*w.all_pix2world(gx, gy, 1), *pix2sky(gx, gy, lay[c], expo)).ravel()
        rstar.append(rs); rgrid.append(rg); chipmax.append(rg.max())
        fluxscale.append((e, hs[c].get("FLXSCALE", np.nan)))
    rs, rg = np.concatenate(rstar), np.concatenate(rgrid)
    allstar.append(rs); allgrid.append(rg)
    wc = int(np.argmax(chipmax))
    d = dict(exp=e + 1, star_rms=float(np.sqrt(np.mean(rs ** 2))), star_max=float(rs.max()),
             grid_rms=float(np.sqrt(np.mean(rg ** 2))), grid_max=float(rg.max()),
             worst_chip=wc + 1, chip_gridmax=[float(v) for v in chipmax])
    res["exposures"].append(d)
    if not args.quiet:
        print("exp%-2d %10.4f %10.4f %10.4f %10.4f   %2d (%.4f)" % (e + 1, d["star_rms"],
              d["star_max"], d["grid_rms"], d["grid_max"], wc + 1, chipmax[wc]))
rs, rg = np.concatenate(allstar), np.concatenate(allgrid)
res.update(star_rms=float(np.sqrt(np.mean(rs ** 2))), star_max=float(rs.max()),
           grid_rms=float(np.sqrt(np.mean(rg ** 2))), grid_max=float(rg.max()))

# photometry: FLXSCALE (identical for all chips of an exposure) vs injected ZP offsets
fs = np.array([np.nanmean([f for ee, f in fluxscale if ee == e]) for e in range(nexp)])
fsspread = max(np.nanmax([f for ee, f in fluxscale if ee == e]) /
               np.nanmin([f for ee, f in fluxscale if ee == e]) for e in range(nexp))
dmag = -2.5 * np.log10(fs / np.nanmean(fs))
dzp = (t["zp_off"] - t["zp_off"].mean()) + (dmag - dmag.mean())
res.update(zp_err_max=float(np.nanmax(np.abs(dzp))), flxscale_chip_spread=float(fsspread))

print("ALL   stars: rms %.4f max %.4f mas | grid: rms %.4f max %.4f mas | "
      "ZP err max %.5f mag" % (res["star_rms"], res["star_max"], res["grid_rms"],
                               res["grid_max"], res["zp_err_max"]))
if args.json:
    json.dump(res, open(args.json, "w"), indent=1)

ok = True
for lim, val, name in ((args.max_rms, res["star_rms"], "rms at stars"),
                       (args.max_grid, res["grid_max"], "max on grid"),
                       (args.max_dzp, res["zp_err_max"], "zero-point error")):
    if lim is not None:
        good = val < lim
        print("%-18s %.4f < %g ... %s" % (name, val, lim, "passed" if good else "FAILED"))
        ok &= good
sys.exit(0 if ok else 1)
