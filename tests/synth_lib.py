"""
Shared definitions for the synthetic SCAMP test data generators
(gen_synth.py, gen_synth_pm.py): instrument geometry, the TRUE
pixel<->sky mapping (TAN plus a radial cubic distortion) and a minimal
FITS-LDAC writer.
"""
import numpy as np
from astropy.io import fits

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
