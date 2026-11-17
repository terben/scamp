#!/usr/bin/env python3
"""
Generate a synthetic multichip (OmegaCAM-like, 8x4 CCDs) SCAMP test data set.

- NEXP dithered exposures; one multi-extension FITS-LDAC catalog per exposure
  (32 LDAC_IMHEAD/LDAC_OBJECTS pairs)
- TRUE mapping: rigid chip layout (perturbed w.r.t. the nominal one) +
  instrument distortion (radial cubic + quadratic terms) + TAN, see mosaic_lib.py
- headers: plain TAN WCS from the NOMINAL layout, without distortion, with
  pointing and position angle errors (what SCAMP has to fix)
- per-exposure photometric zero-point offsets
- a reference catalog (Gaia-like) of the brighter stars
- --noise 0 gives exact centroids and reference positions (the error columns
  are the same as with noise, so that the weighting is unchanged)
The ground truth is saved to truth.npz (see check_mosaic.py).

Usage:  gen_synth_mosaic.py OUTDIR [--noise 0|1] [--seed N] [--k3var F] ...
"""
import sys, os, argparse
import numpy as np
from astropy.io import fits

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mosaic_lib import *

ap = argparse.ArgumentParser()
ap.add_argument("outdir")
ap.add_argument("--noise", type=int, default=1, help="centroid/reference noise on (1) or off (0)")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--ra0", type=float, default=150.10)
ap.add_argument("--dec0", type=float, default=2.20)
ap.add_argument("--nstar", type=int, default=60000)
ap.add_argument("--nexp", type=int, default=6)
ap.add_argument("--k3var", type=float, default=0.0,
                help="relative rms variation of the radial distortion between exposures")
ap.add_argument("--dscale", type=float, default=1.0,
                help="scale factor for the instrument distortion (0 = none)")
ap.add_argument("--same-epoch", action="store_true",
                help="give all exposures the same MJD-OBS")
ap.add_argument("--refsig", type=float, default=15.0, help="reference catalog error (mas)")
ap.add_argument("--refmaglim", type=float, default=20.0)
ap.add_argument("--hdr-pos", type=float, default=3.0, help="header pointing error rms (arcsec)")
ap.add_argument("--hdr-pa", type=float, default=0.02, help="header position angle error rms (deg)")
args = ap.parse_args()

os.makedirs(args.outdir, exist_ok=True)
rng = np.random.default_rng(args.seed)
RA0, DEC0, cosd0 = args.ra0, args.dec0, np.cos(args.dec0 * D2R)
FWHM = 4.0
ZP = 30.0

# ---------------- true sky (uniform in the tangent plane) ----------------
half = 0.75                                   # deg: field + dithers
xi, eta = rng.uniform(-half, half, (2, args.nstar))
ra_s, dec_s = tan2sky(xi, eta, RA0, DEC0)
u_ = rng.uniform(0, 1, args.nstar)
a = 0.3 * np.log(10)
mag_s = 16.0 + np.log(1 + u_ * (np.exp(a * 7.0) - 1)) / a

# ---------------- reference catalog ----------------
sel = mag_s < args.refmaglim
nref = sel.sum()
sig = args.refsig / 3.6e6
ref_ra, ref_dec = ra_s[sel].copy(), dec_s[sel].copy()
if args.noise:
    ref_dec += rng.normal(0, sig, nref)
    ref_ra += rng.normal(0, sig, nref) / np.cos(ref_dec * D2R)
ref_mag = mag_s[sel] + (rng.normal(0, 0.005, nref) if args.noise else 0.0)
refhead = [card("SIMPLE", True), card("BITPIX", 0), card("NAXIS", 2),
           card("NAXIS1", 32768), card("NAXIS2", 32768), card("EXTEND", True),
           card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
           card("CTYPE1", "RA---STG"), card("CRVAL1", RA0), card("CRPIX1", 16384.5),
           card("CD1_1", -5.555555555556e-05), card("CD1_2", 0.0),
           card("CTYPE2", "DEC--STG"), card("CRVAL2", DEC0), card("CRPIX2", 16384.5),
           card("CD2_1", 0.0), card("CD2_2", 5.555555555556e-05)]
ldac_write_mef(os.path.join(args.outdir, "ref.cat"), [(refhead, [
    fits.Column(name="X_WORLD", format="1D", unit="deg", array=ref_ra),
    fits.Column(name="Y_WORLD", format="1D", unit="deg", array=ref_dec),
    fits.Column(name="ERRA_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="ERRB_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="ERRTHETA_WORLD", format="1E", unit="deg", array=np.zeros(nref)),
    fits.Column(name="MAG", format="1E", unit="mag", array=ref_mag),
    fits.Column(name="MAGERR", format="1E", unit="mag", array=np.full(nref, 0.005)),
    fits.Column(name="OBSDATE", format="1D", unit="yr", array=np.full(nref, 2016.0)),
])])

# ---------------- camera ----------------
lay_true = true_layout(rng)
lay_nom = nominal_layout()
nchip = len(lay_nom)

# ---------------- exposures ----------------
dithers = [(0, 0), (60, 100), (-60, 200), (120, -100), (-120, -200), (500, 300),
           (-400, 250), (250, -450)][:args.nexp]                       # arcsec
zp_off = rng.uniform(-0.1, 0.1, args.nexp)
zp_off -= zp_off.mean()
truth = dict(ra=ra_s, dec=dec_s, mag=mag_s, zp_off=zp_off, layout=lay_true,
             layout_nom=lay_nom, noise=args.noise)
expos = []
for e in range(args.nexp):
    xi0, eta0 = dithers[e][0] / 3600.0, dithers[e][1] / 3600.0
    ra0, dec0 = tan2sky(xi0, eta0, RA0, DEC0)
    expo = dict(ra0=float(ra0), dec0=float(dec0), pa=float(rng.normal(0, 0.005)),
                k3=args.dscale * K3 * (1 + args.k3var * rng.normal()), qs=args.dscale)
    expos.append(expo)
    # header pointing/position angle (with errors)
    off = rng.normal(0, args.hdr_pos, 2) / 3600.0
    ra_h, dec_h = ra0 + off[0] / np.cos(dec0 * D2R), dec0 + off[1]
    pa_h = expo["pa"] + rng.normal(0, args.hdr_pa)
    cpa, spa = np.cos(pa_h * D2R), np.sin(pa_h * D2R)
    rpa = np.array([[cpa, -spa], [spa, cpa]])

    fx, fy = sky2focal(ra_s, dec_s, expo)
    exts = []
    nall = 0
    for c in range(nchip):
        x, y = focal2chip(fx, fy, lay_true[c])
        inside = (x > 10) & (x < NAXIS1 - 10) & (y > 10) & (y < NAXIS2 - 10)
        idx = np.nonzero(inside)[0]
        x, y = x[idx], y[idx]
        n = idx.size
        nall += n
        flux = 10 ** (-0.4 * (mag_s[idx] - ZP + zp_off[e]))
        snr = 10.0 * 10 ** (-0.4 * (mag_s[idx] - 23.0))
        snr = snr / np.sqrt(1 + snr / 3000.0)
        fluxerr = flux / snr
        perr = np.sqrt((0.6 * FWHM / snr) ** 2 + 0.003 ** 2)        # pixels
        if args.noise:
            flux_obs = flux + rng.normal(0, 1, n) * fluxerr
            xo = x + rng.normal(0, 1, n) * perr
            yo = y + rng.normal(0, 1, n) * perr
        else:
            flux_obs, xo, yo = flux, x, y
        # header WCS from the nominal layout, no distortion
        ang = lay_nom[c, 2] * D2R
        rchip = np.array([[np.cos(ang), -np.sin(ang)], [np.sin(ang), np.cos(ang)]])
        cd = rpa @ np.diag([-PIXSCALE, PIXSCALE]) @ rchip
        crpix = focal2chip(0.0, 0.0, lay_nom[c])
        head = [card("XTENSION", "IMAGE"), card("BITPIX", -32), card("NAXIS", 2),
                card("NAXIS1", NAXIS1), card("NAXIS2", NAXIS2), card("PCOUNT", 0),
                card("GCOUNT", 1), card("EXTNAME", "CCD_%02d" % (c + 1)),
                card("OBJECT", "SYNTH"), card("FILTER", "r"), card("EXPTIME", 100.0),
                card("AIRMASS", 1.0),
                card("MJD-OBS", 60000.0 + (0.0 if args.same_epoch else 0.01 * e)),
                card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
                card("CTYPE1", "RA---TAN"), card("CTYPE2", "DEC--TAN"),
                card("CUNIT1", "deg"), card("CUNIT2", "deg"),
                card("CRVAL1", ra_h), card("CRVAL2", dec_h),
                card("CRPIX1", crpix[0]), card("CRPIX2", crpix[1]),
                card("CD1_1", cd[0, 0]), card("CD1_2", cd[0, 1]),
                card("CD2_1", cd[1, 0]), card("CD2_2", cd[1, 1]),
                card("GAIN", 1.0), card("SATURATE", 60000.0)]
        exts.append((head, [
            fits.Column(name="NUMBER", format="1J", array=np.arange(1, n + 1)),
            fits.Column(name="X_IMAGE", format="1D", unit="pixel", array=xo),
            fits.Column(name="Y_IMAGE", format="1D", unit="pixel", array=yo),
            fits.Column(name="XWIN_IMAGE", format="1D", unit="pixel", array=xo),
            fits.Column(name="YWIN_IMAGE", format="1D", unit="pixel", array=yo),
            fits.Column(name="ERRAWIN_IMAGE", format="1E", unit="pixel", array=perr),
            fits.Column(name="ERRBWIN_IMAGE", format="1E", unit="pixel", array=perr),
            fits.Column(name="ERRTHETAWIN_IMAGE", format="1E", unit="deg", array=np.zeros(n)),
            fits.Column(name="FLUX_AUTO", format="1E", unit="count", array=flux_obs),
            fits.Column(name="FLUXERR_AUTO", format="1E", unit="count", array=fluxerr),
            fits.Column(name="MAG_AUTO", format="1E", unit="mag",
                        array=ZP - 2.5 * np.log10(np.clip(flux_obs, 1e-3, None))),
            fits.Column(name="FLUX_RADIUS", format="1E", unit="pixel",
                        array=np.full(n, FWHM / 2)),
            fits.Column(name="FLAGS", format="1I", array=np.zeros(n, dtype=np.int16)),
        ]))
        truth["idx%d_%d" % (e, c)] = idx
        truth["x%d_%d" % (e, c)] = x
        truth["y%d_%d" % (e, c)] = y
    ldac_write_mef(os.path.join(args.outdir, "exp%d.cat" % (e + 1)), exts)
    print("exp%d.cat: %d detections on %d chips, header offset (%.1f\", %.1f\"), "
          "PA error %.3f deg, ZP offset %+.3f mag"
          % (e + 1, nall, nchip, off[0] * 3600, off[1] * 3600, pa_h - expo["pa"], zp_off[e]))

truth["expo"] = np.array([[x["ra0"], x["dec0"], x["pa"], x["k3"], x["qs"]] for x in expos])
print("ref.cat: %d reference stars (mag < %.1f, sigma %.0f mas, noise %s)"
      % (nref, args.refmaglim, args.refsig, "on" if args.noise else "off"))
np.savez(os.path.join(args.outdir, "truth.npz"), **truth)
