#!/usr/bin/env python3
"""
Generate a synthetic multi-epoch SCAMP test data set with proper motions
(FITS-LDAC catalogues).

- NEXP dithered exposures of a single 4096x4096 CCD, spread over 8 years
- stars move: 80% with small proper motions (sigma 5 mas/yr), 20% fast
  movers (sigma 60 mas/yr per axis)
- a reference catalogue (Gaia-like) of the brighter stars at epoch 2016,
  with proper motions and their uncertainties
- same true pixel->sky mapping and header errors as gen_synth.py
The ground truth (positions at epoch 2016, proper motions) is saved to
truth.npz. Used by test_propmotion01.py.

Usage:  python3 gen_synth_pm.py <output directory>

Requires numpy and astropy (see requirements.txt).
"""
import sys, os
import numpy as np
from astropy.io import fits

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth_lib import *

outdir = sys.argv[1]
os.makedirs(outdir, exist_ok=True)
rng = np.random.default_rng(7)

NEXP = 8
EPOCHS = np.linspace(2014.0, 2022.0, NEXP)
REFEPOCH = 2016.0
PMERR_REF = 0.5                    # mas/yr
MAS = 1.0 / 3.6e6                  # deg

# ---------------- true sky at the reference epoch ----------------
half = 0.36
ra_s = RA0 + rng.uniform(-half, half, NSTAR) / np.cos(DEC0 * D2R)
dec_s = DEC0 + rng.uniform(-half, half, NSTAR)
u_ = rng.uniform(0, 1, NSTAR)
a = 0.3 * np.log(10)
mag_s = 16.0 + np.log(1 + u_ * (np.exp(a * 7.0) - 1)) / a
fast = rng.uniform(0, 1, NSTAR) < 0.2
# mu_alpha*cos(delta) and mu_delta, mas/yr
pmra = np.where(fast, rng.normal(0, 60, NSTAR), rng.normal(0, 5, NSTAR))
pmde = np.where(fast, rng.normal(0, 60, NSTAR), rng.normal(0, 5, NSTAR))

def pos_at(epoch):
    dt = epoch - REFEPOCH
    return (ra_s + pmra * dt * MAS / np.cos(dec_s * D2R),
            dec_s + pmde * dt * MAS)

# ---------------- reference catalogue ----------------
sel = mag_s < REFMAGLIM
nref = sel.sum()
sig = REFSIG_MAS * MAS
refhead = [card("SIMPLE", True), card("BITPIX", 0), card("NAXIS", 2),
           card("NAXIS1", 16384), card("NAXIS2", 16384), card("EXTEND", True),
           card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
           card("CTYPE1", "RA---STG"), card("CRVAL1", RA0), card("CRPIX1", 8192.5),
           card("CD1_1", 5.555555555556e-05), card("CD1_2", 0.0),
           card("CTYPE2", "DEC--STG"), card("CRVAL2", DEC0), card("CRPIX2", 8192.5),
           card("CD2_1", 0.0), card("CD2_2", 5.555555555556e-05)]
ldac_write(os.path.join(outdir, "ref.cat"), refhead, [
    fits.Column(name="X_WORLD", format="1D", unit="deg",
                array=ra_s[sel] + rng.normal(0, sig, nref) / np.cos(dec_s[sel] * D2R)),
    fits.Column(name="Y_WORLD", format="1D", unit="deg",
                array=dec_s[sel] + rng.normal(0, sig, nref)),
    fits.Column(name="ERRA_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="ERRB_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="MAG", format="1E", unit="mag", array=mag_s[sel]),
    fits.Column(name="MAGERR", format="1E", unit="mag", array=np.full(nref, 0.005)),
    fits.Column(name="OBSDATE", format="1D", unit="yr", array=np.full(nref, REFEPOCH)),
    fits.Column(name="PMALPHA_J2000", format="1E", unit="mas/yr",
                array=pmra[sel] + rng.normal(0, PMERR_REF, nref)),
    fits.Column(name="PMDELTA_J2000", format="1E", unit="mas/yr",
                array=pmde[sel] + rng.normal(0, PMERR_REF, nref)),
    fits.Column(name="PMALPHAERR_J2000", format="1E", unit="mas/yr",
                array=np.full(nref, PMERR_REF)),
    fits.Column(name="PMDELTAERR_J2000", format="1E", unit="mas/yr",
                array=np.full(nref, PMERR_REF)),
])

# ---------------- exposures ----------------
dithers = [(0, 0), (60, 45), (-60, 50), (55, -60), (-50, -55),
           (30, -20), (-25, 35), (10, 60)]                  # arcsec
ZP = 30.0
for e in range(NEXP):
    crval = (RA0 + dithers[e][0] / 3600.0 / np.cos(DEC0 * D2R),
             DEC0 + dithers[e][1] / 3600.0)
    rot = rng.normal(0, 0.01)
    ra_t, dec_t = pos_at(EPOCHS[e])
    x, y = true_sky2pix(ra_t, dec_t, crval, rot)
    inside = (x > 10) & (x < NPIX - 10) & (y > 10) & (y < NPIX - 10)
    idx = np.nonzero(inside)[0]
    n = idx.size
    flux = 10 ** (-0.4 * (mag_s[idx] - ZP))
    snr = 10.0 * 10 ** (-0.4 * (mag_s[idx] - 23.0))
    snr = snr / np.sqrt(1 + snr / 3000.0)
    fluxerr = flux / snr
    flux_obs = flux + rng.normal(0, 1, n) * fluxerr
    perr = np.sqrt((0.6 * FWHM / snr) ** 2 + 0.003 ** 2)  # pixels
    xo = x[idx] + rng.normal(0, 1, n) * perr
    yo = y[idx] + rng.normal(0, 1, n) * perr
    off = rng.normal(0, 4.0, 2) / 3600.0
    crval_hdr = (crval[0] + off[0] / np.cos(DEC0 * D2R), crval[1] + off[1])
    cd = cdmatrix(rot + rng.normal(0, 0.03))
    mjd = 51544.5 + (EPOCHS[e] - 2000.0) * 365.25
    head = [card("XTENSION", "IMAGE"), card("BITPIX", -32), card("NAXIS", 2),
            card("NAXIS1", NPIX), card("NAXIS2", NPIX), card("PCOUNT", 0), card("GCOUNT", 1),
            card("OBJECT", "SYNTH"), card("FILTER", "r"), card("EXPTIME", 100.0),
            card("AIRMASS", 1.0), card("MJD-OBS", mjd),
            card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
            card("CTYPE1", "RA---TAN"), card("CTYPE2", "DEC--TAN"),
            card("CUNIT1", "deg"), card("CUNIT2", "deg"),
            card("CRVAL1", crval_hdr[0]), card("CRVAL2", crval_hdr[1]),
            card("CRPIX1", CRPIX), card("CRPIX2", CRPIX),
            card("CD1_1", cd[0, 0]), card("CD1_2", cd[0, 1]),
            card("CD2_1", cd[1, 0]), card("CD2_2", cd[1, 1]),
            card("GAIN", 1.0), card("SATURATE", 60000.0)]
    ldac_write(os.path.join(outdir, "exp%d.cat" % (e + 1)), head, [
        fits.Column(name="NUMBER", format="1J", array=np.arange(1, n + 1)),
        fits.Column(name="XWIN_IMAGE", format="1D", unit="pixel", array=xo),
        fits.Column(name="YWIN_IMAGE", format="1D", unit="pixel", array=yo),
        fits.Column(name="ERRAWIN_IMAGE", format="1E", unit="pixel", array=perr),
        fits.Column(name="ERRBWIN_IMAGE", format="1E", unit="pixel", array=perr),
        fits.Column(name="ERRTHETAWIN_IMAGE", format="1E", unit="deg", array=np.zeros(n)),
        fits.Column(name="FLUX_AUTO", format="1E", unit="count", array=flux_obs),
        fits.Column(name="FLUXERR_AUTO", format="1E", unit="count", array=fluxerr),
        fits.Column(name="MAG_AUTO", format="1E", unit="mag",
                    array=ZP - 2.5 * np.log10(np.clip(flux_obs, 1e-3, None))),
        fits.Column(name="FLUX_RADIUS", format="1E", unit="pixel", array=np.full(n, FWHM / 2)),
        fits.Column(name="FLAGS", format="1I", array=np.zeros(n, dtype=np.int16)),
    ])
    print("exp%d.cat: epoch %.1f, %d detections" % (e + 1, EPOCHS[e], n))

print("ref.cat: %d reference stars at epoch %.1f" % (nref, REFEPOCH))
np.savez(os.path.join(outdir, "truth.npz"),
         ra=ra_s, dec=dec_s, mag=mag_s, pmra=pmra, pmde=pmde,
         epochs=EPOCHS, refepoch=REFEPOCH)
