#!/usr/bin/env python3
"""
Generate a synthetic SCAMP test data set (FITS-LDAC catalogues).

- NEXP dithered exposures of a single 4096x4096 CCD, 0.2"/pixel
- the TRUE pixel->sky mapping is TAN plus a radial cubic distortion
- the catalogue headers only carry a plain TAN WCS with a deliberate
  pointing offset and rotation error (what SCAMP has to fix)
- per-exposure photometric zero-point offsets (what SCAMP should recover)
- a reference catalogue (Gaia-like) of the brighter stars
The ground truth is saved to truth.npz for later verification.

Usage (from the tests/ directory, after building SCAMP):

  python3 gen_synth.py synth              # writes synth/exp?.cat, ref.cat, truth.npz
  cd synth && ../../src/scamp -dd > default.scamp
  ../../src/scamp exp?.cat -c default.scamp \
      -ASTREF_CATALOG FILE -ASTREFCAT_NAME ref.cat \
      -ASTREFCENT_KEYS X_WORLD,Y_WORLD \
      -ASTREFERR_KEYS ERRA_WORLD,ERRB_WORLD,ERRTHETA_WORLD \
      -ASTREFMAG_KEY MAG -ASTREFMAGERR_KEY MAGERR -ASTREFOBSDATE_KEY OBSDATE \
      -ASTRINSTRU_KEY FILTER -PHOTINSTRU_KEY FILTER -DISTORT_DEGREES 3 \
      -XML_NAME synth.xml
  cd .. && python3 check_synth.py synth   # exit status 0 = passed

Requires numpy and astropy (see requirements.txt).
"""
import sys, os
import numpy as np
from astropy.io import fits

outdir = sys.argv[1]
os.makedirs(outdir, exist_ok=True)
rng = np.random.default_rng(42)

RA0, DEC0 = 150.10, 2.20          # field centre (deg)
NPIX = 4096
PIXSCALE = 0.2 / 3600.0           # deg / pixel
CRPIX = (NPIX + 1) / 2.0
KDIST = 0.07                      # radial distortion coefficient (deg^-2)
NSTAR = 20000
NEXP = 5
FWHM = 4.0                        # pixels
REFMAGLIM = 20.0
REFSIG_MAS = 15.0

D2R = np.pi / 180.0

# ---------------- TAN projection helpers (deg) ----------------
def sky2tan(ra, dec, ra0, dec0):
    ra, dec, ra0, dec0 = [x * D2R for x in (ra, dec, ra0, dec0)]
    cosc = np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0)
    xi = np.cos(dec) * np.sin(ra - ra0) / cosc
    eta = (np.cos(dec0) * np.sin(dec) - np.sin(dec0) * np.cos(dec) * np.cos(ra - ra0)) / cosc
    return xi / D2R, eta / D2R

def tan2sky(xi, eta, ra0, dec0):
    xi, eta, ra0, dec0 = xi * D2R, eta * D2R, ra0 * D2R, dec0 * D2R
    rho = np.hypot(xi, eta)
    c = np.arctan(rho)
    with np.errstate(invalid="ignore", divide="ignore"):
        dec = np.arcsin(np.cos(c) * np.sin(dec0) +
                        np.where(rho > 0, eta * np.sin(c) * np.cos(dec0) / rho, 0.0))
    ra = ra0 + np.arctan2(xi * np.sin(c),
                          rho * np.cos(dec0) * np.cos(c) - eta * np.sin(dec0) * np.sin(c))
    return (ra / D2R) % 360.0, dec / D2R

def cdmatrix(rot_deg):
    t = rot_deg * D2R
    # RA increases to the left (East left) -> negative CD1_1
    return PIXSCALE * np.array([[-np.cos(t), np.sin(t)],
                                [np.sin(t), np.cos(t)]])

# TRUE mapping: pixel -> intermediate (u,v) -> distortion -> TAN -> sky
def true_sky2pix(ra, dec, crval, rot):
    xi, eta = sky2tan(ra, dec, *crval)
    # invert (u,v)*(1+K r^2) = (xi,eta) iteratively
    u, v = xi.copy(), eta.copy()
    for _ in range(20):
        f = 1.0 + KDIST * (u * u + v * v)
        u, v = xi / f, eta / f
    cdi = np.linalg.inv(cdmatrix(rot))
    x = cdi[0, 0] * u + cdi[0, 1] * v + CRPIX
    y = cdi[1, 0] * u + cdi[1, 1] * v + CRPIX
    return x, y

def true_pix2sky(x, y, crval, rot):
    cd = cdmatrix(rot)
    u = cd[0, 0] * (x - CRPIX) + cd[0, 1] * (y - CRPIX)
    v = cd[1, 0] * (x - CRPIX) + cd[1, 1] * (y - CRPIX)
    f = 1.0 + KDIST * (u * u + v * v)
    return tan2sky(u * f, v * f, *crval)

# ---------------- LDAC writer ----------------
def ldac_write(fname, header_cards, cols):
    cards = [c.ljust(80)[:80] for c in header_cards] + ["END".ljust(80)]
    n = len(cards)
    imhead = fits.BinTableHDU.from_columns(
        [fits.Column(name="Field Header Card", format="%dA" % (80 * n),
                     array=np.array(["".join(cards)]))], name="LDAC_IMHEAD")
    imhead.header["TDIM1"] = "(80, %d)" % n
    objects = fits.BinTableHDU.from_columns(cols, name="LDAC_OBJECTS")
    fits.HDUList([fits.PrimaryHDU(), imhead, objects]).writeto(fname, overwrite=True)
    # astropy strips trailing blanks of string cells and pads with NULs;
    # restore the blank-padded END card that FITS (and SCAMP) expects
    raw = open(fname, "rb").read()
    bad = b"END" + b"\x00" * 77
    assert raw.count(bad) == 1, fname
    open(fname, "wb").write(raw.replace(bad, b"END" + b" " * 77))

def card(key, val, comment=""):
    return fits.Card(key, val, comment).image

# ---------------- true sky ----------------
half = 0.36   # deg, covers all dithers
ra_s = RA0 + rng.uniform(-half, half, NSTAR) / np.cos(DEC0 * D2R)
dec_s = DEC0 + rng.uniform(-half, half, NSTAR)
# power-law magnitude distribution between 16 and 23
u_ = rng.uniform(0, 1, NSTAR)
a = 0.3 * np.log(10)
mag_s = 16.0 + np.log(1 + u_ * (np.exp(a * 7.0) - 1)) / a

# ---------------- reference catalogue ----------------
sel = mag_s < REFMAGLIM
nref = sel.sum()
sig = REFSIG_MAS / 3.6e6
ref_ra = ra_s[sel] + rng.normal(0, sig, nref) / np.cos(dec_s[sel] * D2R)
ref_dec = dec_s[sel] + rng.normal(0, sig, nref)
ref_mag = mag_s[sel] + rng.normal(0, 0.005, nref)
refhead = [card("SIMPLE", True), card("BITPIX", 0), card("NAXIS", 2),
           card("NAXIS1", 16384), card("NAXIS2", 16384), card("EXTEND", True),
           card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
           card("CTYPE1", "RA---STG"), card("CRVAL1", RA0), card("CRPIX1", 8192.5),
           card("CD1_1", 5.555555555556e-05), card("CD1_2", 0.0),
           card("CTYPE2", "DEC--STG"), card("CRVAL2", DEC0), card("CRPIX2", 8192.5),
           card("CD2_1", 0.0), card("CD2_2", 5.555555555556e-05)]
ldac_write(os.path.join(outdir, "ref.cat"), refhead, [
    fits.Column(name="X_WORLD", format="1D", unit="deg", array=ref_ra),
    fits.Column(name="Y_WORLD", format="1D", unit="deg", array=ref_dec),
    fits.Column(name="ERRA_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="ERRB_WORLD", format="1E", unit="deg", array=np.full(nref, sig)),
    fits.Column(name="MAG", format="1E", unit="mag", array=ref_mag),
    fits.Column(name="MAGERR", format="1E", unit="mag", array=np.full(nref, 0.005)),
    fits.Column(name="OBSDATE", format="1D", unit="yr", array=np.full(nref, 2016.0)),
])

# ---------------- exposures ----------------
dithers = [(0, 0), (60, 45), (-60, 50), (55, -60), (-50, -55)]   # arcsec
zp_off = rng.uniform(-0.1, 0.1, NEXP)
zp_off -= zp_off.mean()
truth = dict(ra=ra_s, dec=dec_s, mag=mag_s, zp_off=zp_off, kdist=KDIST,
             crval=[], rot=[], idx=[], xtrue=[], ytrue=[], crval_hdr=[], rot_hdr=[])

ZP = 30.0
for e in range(NEXP):
    crval = (RA0 + dithers[e][0] / 3600.0 / np.cos(DEC0 * D2R),
             DEC0 + dithers[e][1] / 3600.0)
    rot = rng.normal(0, 0.01)
    x, y = true_sky2pix(ra_s, dec_s, crval, rot)
    inside = (x > 10) & (x < NPIX - 10) & (y > 10) & (y < NPIX - 10)
    idx = np.nonzero(inside)[0]
    n = idx.size
    flux = 10 ** (-0.4 * (mag_s[idx] - ZP + zp_off[e]))
    snr = 10.0 * 10 ** (-0.4 * (mag_s[idx] - 23.0))
    snr = snr / np.sqrt(1 + snr / 3000.0)              # brighter -> saturating S/N
    fluxerr = flux / snr
    flux_obs = flux + rng.normal(0, 1, n) * fluxerr
    perr = np.sqrt((0.6 * FWHM / snr) ** 2 + 0.003 ** 2)  # pixels
    xo = x[idx] + rng.normal(0, 1, n) * perr
    yo = y[idx] + rng.normal(0, 1, n) * perr
    # header WCS: plain TAN, pointing off by a few arcsec, rotation off
    off = rng.normal(0, 4.0, 2) / 3600.0
    crval_hdr = (crval[0] + off[0] / np.cos(DEC0 * D2R), crval[1] + off[1])
    rot_hdr = rot + rng.normal(0, 0.03)
    cd = cdmatrix(rot_hdr)
    head = [card("XTENSION", "IMAGE"), card("BITPIX", -32), card("NAXIS", 2),
            card("NAXIS1", NPIX), card("NAXIS2", NPIX), card("PCOUNT", 0), card("GCOUNT", 1),
            card("OBJECT", "SYNTH"), card("FILTER", "r"), card("EXPTIME", 100.0),
            card("AIRMASS", 1.0), card("MJD-OBS", 60000.0 + 0.01 * e),
            card("EQUINOX", 2000.0), card("RADESYS", "ICRS"),
            card("CTYPE1", "RA---TAN"), card("CTYPE2", "DEC--TAN"),
            card("CUNIT1", "deg"), card("CUNIT2", "deg"),
            card("CRVAL1", crval_hdr[0]), card("CRVAL2", crval_hdr[1]),
            card("CRPIX1", CRPIX), card("CRPIX2", CRPIX),
            card("CD1_1", cd[0, 0]), card("CD1_2", cd[0, 1]),
            card("CD2_1", cd[1, 0]), card("CD2_2", cd[1, 1]),
            card("GAIN", 1.0), card("SATURATE", 60000.0)]
    errdeg = perr * PIXSCALE
    ldac_write(os.path.join(outdir, "exp%d.cat" % (e + 1)), head, [
        fits.Column(name="NUMBER", format="1J", array=np.arange(1, n + 1)),
        fits.Column(name="X_IMAGE", format="1E", unit="pixel", array=xo),
        fits.Column(name="Y_IMAGE", format="1E", unit="pixel", array=yo),
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
    truth["crval"].append(crval); truth["rot"].append(rot)
    truth["crval_hdr"].append(crval_hdr); truth["rot_hdr"].append(rot_hdr)
    truth["idx"].append(idx); truth["xtrue"].append(x[idx]); truth["ytrue"].append(y[idx])
    print("exp%d.cat: %d detections, header offset (%.1f\", %.1f\"), rot error %.3f deg, "
          "ZP offset %+.3f mag" % (e + 1, n, off[0] * 3600, off[1] * 3600, rot_hdr - rot, zp_off[e]))

print("ref.cat: %d reference stars (mag < %.1f, sigma %.0f mas)" % (nref, REFMAGLIM, REFSIG_MAS))
np.savez(os.path.join(outdir, "truth.npz"),
         ra=ra_s, dec=dec_s, mag=mag_s, zp_off=zp_off,
         crval=np.array(truth["crval"]), rot=np.array(truth["rot"]),
         **{"idx%d" % i: v for i, v in enumerate(truth["idx"])},
         **{"x%d" % i: v for i, v in enumerate(truth["xtrue"])},
         **{"y%d" % i: v for i, v in enumerate(truth["ytrue"])})
