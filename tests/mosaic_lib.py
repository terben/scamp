"""
Ground-truth model of a synthetic OmegaCAM-like multichip camera, shared by
gen_synth_mosaic.py (data generation) and check_mosaic.py (verification).

Geometry (loosely after OmegaCAM at the VST):
  8 x 4 CCDs of 2048 x 4100 pixels, 0.214"/pixel, ~1 deg x 1 deg field;
  inter-chip gaps of ~26" (x) and ~86" (y); the CCDs of the upper two rows
  are rotated by 180 deg (opposite read-out direction).
  Every chip is displaced and rotated by a small amount with respect to the
  nominal layout; the catalog headers only know the nominal layout.

TRUE mapping chip pixel -> sky:
  chip pixel (x,y) -> focal plane pixels (fx,fy) [rigid: offset + rotation]
  -> instrument coordinates (p,q) in deg [scale, East left]
  -> distortion (p',q') = (p,q) (1 + K r^2) + quadratic terms
  -> rotation by the exposure position angle -> (xi,eta)
  -> gnomonic (TAN) projection around the exposure pointing.
The composition is a polynomial of degree 3 in the pixel coordinates of
each chip, i.e. exactly representable by SCAMP's TPV polynomials with
DISTORT_DEGREES >= 3.
"""
import numpy as np
from astropy.io import fits

D2R = np.pi / 180.0
NCHIPX, NCHIPY = 8, 4
NAXIS1, NAXIS2 = 2048, 4100
PIXSCALE = 0.214 / 3600.0               # deg / pixel
GAPX, GAPY = 120.0, 400.0               # pixels (~26", ~86")

# Distortion fixed to the instrument (instrument coordinates in deg)
K3 = 0.012          # radial cubic (deg^-2): ~11" at the field corner (r=0.69 deg)
Q_UV = 1.5e-3       # p' += Q_UV * p q          (deg^-1): ~0.7" at the corner
Q_UU = 1.0e-3       # q' += Q_UU * (p^2 - q^2)  (deg^-1)


def nominal_layout():
    """Nominal chip centres (focal plane pixels) and orientation (0 or 180 deg)."""
    cx = (np.arange(NCHIPX) - (NCHIPX - 1) / 2.0) * (NAXIS1 + GAPX)
    cy = (np.arange(NCHIPY) - (NCHIPY - 1) / 2.0) * (NAXIS2 + GAPY)
    chips = []
    for j in range(NCHIPY):
        for i in range(NCHIPX):
            chips.append((cx[i], cy[j], 180.0 if j >= NCHIPY // 2 else 0.0))
    return np.array(chips)          # (32, 3): fx0, fy0, angle (deg)


def true_layout(rng, sig_off=5.0, sig_rot=0.02):
    """Actual layout: nominal + random offsets (pixels) and rotations (deg)."""
    lay = nominal_layout()
    lay[:, 0] += rng.normal(0, sig_off, len(lay))
    lay[:, 1] += rng.normal(0, sig_off, len(lay))
    lay[:, 2] += rng.normal(0, sig_rot, len(lay))
    return lay


CHIPCEN = ((NAXIS1 + 1) / 2.0, (NAXIS2 + 1) / 2.0)


def chip2focal(x, y, chip):
    """chip = (fx0, fy0, angle): chip pixel (1-based) -> focal plane pixels."""
    a = chip[2] * D2R
    dx, dy = x - CHIPCEN[0], y - CHIPCEN[1]
    return (chip[0] + np.cos(a) * dx - np.sin(a) * dy,
            chip[1] + np.sin(a) * dx + np.cos(a) * dy)


def focal2chip(fx, fy, chip):
    a = chip[2] * D2R
    dx, dy = fx - chip[0], fy - chip[1]
    return (CHIPCEN[0] + np.cos(a) * dx + np.sin(a) * dy,
            CHIPCEN[1] - np.sin(a) * dx + np.cos(a) * dy)


def distort(p, q, k3=K3, qs=1.0):
    """qs scales the quadratic (non-radial) terms."""
    r2 = p * p + q * q
    return (p * (1 + k3 * r2) + qs * Q_UV * p * q,
            q * (1 + k3 * r2) + qs * Q_UU * (p * p - q * q))


def undistort(pd, qd, k3=K3, qs=1.0, niter=60):
    p, q = pd.copy(), qd.copy()
    for _ in range(niter):
        dp, dq = distort(p, q, k3, qs)
        p, q = p - (dp - pd), q - (dq - qd)
    return p, q


# ---------------- TAN projection (deg) ----------------
def sky2tan(ra, dec, ra0, dec0):
    ra, dec, ra0, dec0 = [np.asarray(v, float) * D2R for v in (ra, dec, ra0, dec0)]
    cosc = np.sin(dec0) * np.sin(dec) + np.cos(dec0) * np.cos(dec) * np.cos(ra - ra0)
    xi = np.cos(dec) * np.sin(ra - ra0) / cosc
    eta = (np.cos(dec0) * np.sin(dec) - np.sin(dec0) * np.cos(dec) * np.cos(ra - ra0)) / cosc
    return xi / D2R, eta / D2R


def tan2sky(xi, eta, ra0, dec0):
    xi, eta = np.asarray(xi, float) * D2R, np.asarray(eta, float) * D2R
    ra0, dec0 = ra0 * D2R, dec0 * D2R
    den = np.cos(dec0) - eta * np.sin(dec0)
    ra = ra0 + np.arctan2(xi, den)
    dec = np.arctan2(np.sin(dec0) + eta * np.cos(dec0), np.hypot(xi, den))
    return (ra / D2R) % 360.0, dec / D2R


# ---------------- full mapping ----------------
def inst2tan(p, q, pa):
    """Instrument (deg) -> standard coordinates (deg), position angle pa (deg)."""
    c, s = np.cos(pa * D2R), np.sin(pa * D2R)
    return c * p - s * q, s * p + c * q


def tan2inst(xi, eta, pa):
    c, s = np.cos(pa * D2R), np.sin(pa * D2R)
    return c * xi + s * eta, -s * xi + c * eta


def pix2sky(x, y, chip, expo):
    """expo: dict with ra0, dec0, pa, k3, qs."""
    fx, fy = chip2focal(x, y, chip)
    p, q = -fx * PIXSCALE, fy * PIXSCALE          # East left
    p, q = distort(p, q, expo["k3"], expo["qs"])
    return tan2sky(*inst2tan(p, q, expo["pa"]), expo["ra0"], expo["dec0"])


def sky2focal(ra, dec, expo):
    xi, eta = sky2tan(ra, dec, expo["ra0"], expo["dec0"])
    p, q = undistort(*tan2inst(xi, eta, expo["pa"]), expo["k3"], expo["qs"])
    return -p / PIXSCALE, q / PIXSCALE


def sep_mas(ra1, dec1, ra2, dec2):
    """Angular separation (mas), exact (haversine)."""
    ra1, dec1, ra2, dec2 = [np.asarray(v, float) * D2R for v in (ra1, dec1, ra2, dec2)]
    h = np.sin((dec2 - dec1) / 2) ** 2 + np.cos(dec1) * np.cos(dec2) * np.sin((ra2 - ra1) / 2) ** 2
    return 2 * np.arcsin(np.sqrt(h)) / D2R * 3.6e6


# ---------------- FITS-LDAC (multi-extension) ----------------
def card(key, val, comment=""):
    return fits.Card(key, val, comment).image


def ldac_write_mef(fname, exts):
    """exts: list of (header_cards, columns) -> LDAC_IMHEAD/LDAC_OBJECTS pairs."""
    hdus = [fits.PrimaryHDU()]
    for header_cards, cols in exts:
        cards = [c.ljust(80)[:80] for c in header_cards] + ["END".ljust(80)]
        n = len(cards)
        imhead = fits.BinTableHDU.from_columns(
            [fits.Column(name="Field Header Card", format="%dA" % (80 * n),
                         array=np.array(["".join(cards)]))], name="LDAC_IMHEAD")
        imhead.header["TDIM1"] = "(80, %d)" % n
        hdus += [imhead, fits.BinTableHDU.from_columns(cols, name="LDAC_OBJECTS")]
    fits.HDUList(hdus).writeto(fname, overwrite=True)
    # astropy pads string cells with NULs; FITS (and SCAMP) expect a blank-padded END
    raw = open(fname, "rb").read()
    bad = b"END" + b"\x00" * 77
    assert raw.count(bad) == len(exts), fname
    open(fname, "wb").write(raw.replace(bad, b"END" + b" " * 77))


# ---------------- reading SCAMP output ----------------
def read_imheads(cat):
    """Image headers (astropy Header) of all extensions of an LDAC catalog."""
    out = []
    for h in fits.open(cat):
        if h.name != "LDAC_IMHEAD":
            continue
        c = h.data[0][0]
        if not isinstance(c, str):
            c = "".join(s.ljust(80) for s in c)
        out.append(fits.Header.fromstring(c.rstrip("\x00")))
    return out


def read_heads(fn):
    """All header blocks of a SCAMP .head file."""
    blocks = [b for b in open(fn).read().split("\nEND") if "CRVAL1" in b]
    return [fits.Header.fromstring(b.strip("\n") + "\n", sep="\n") for b in blocks]


def scamp_wcs(h0, hs):
    """astropy WCS from the original image header h0 updated with SCAMP's header hs."""
    import warnings
    from astropy.wcs import WCS, FITSFixedWarning
    h = h0.copy()
    for k in list(h.keys()):
        if k.startswith(("PV", "CD", "PC", "CDELT", "CROTA")):
            h.remove(k, ignore_missing=True, remove_all=True)
    h.update(hs)
    if any(k.startswith("PV") for k in hs.keys()):
        # SCAMP writes TAN + PV (TPV convention); tell wcslib explicitly
        h["CTYPE1"], h["CTYPE2"] = "RA---TPV", "DEC--TPV"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FITSFixedWarning)
        return WCS(h)


def expo_from_truth(row):
    """Exposure parameters from a row of truth['expo']."""
    return dict(ra0=row[0], dec0=row[1], pa=row[2], k3=row[3], qs=row[4])
