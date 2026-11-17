#!/usr/bin/env python3
"""
Turn a SCAMP .head file (one exposure of a calibration data set) into .ahead
files carrying the instrument model (chip layout and distortion) for other
exposures of the same camera.

Only the WCS keywords are kept (CTYPE, CUNIT, CRPIX, CD, PV, EQUINOX, RADESYS).
CRVAL is dropped by default, so that the pointing comes from the header of
each image.

Usage: head2ahead.py MODEL.head OUTDIR NAME1 [NAME2 ...] [--keep-crval]
       writes OUTDIR/NAME1.ahead, ...
"""
import sys, os, argparse

ap = argparse.ArgumentParser()
ap.add_argument("head")
ap.add_argument("outdir")
ap.add_argument("names", nargs="+")
ap.add_argument("--keep-crval", action="store_true")
args = ap.parse_args()

keep = ("CTYPE", "CUNIT", "CRPIX", "CD1_", "CD2_", "PV1_", "PV2_", "EQUINOX", "RADESYS")
if args.keep_crval:
    keep += ("CRVAL",)
out = []
for line in open(args.head):
    key = line[:8].strip()
    if key == "END":
        out.append("END".ljust(80) + "\n")
    elif key.startswith(keep):
        out.append(line.rstrip("\n").ljust(80) + "\n")
os.makedirs(args.outdir, exist_ok=True)
for n in args.names:
    open(os.path.join(args.outdir, n + ".ahead"), "w").write("".join(out))
print("%s: %d extensions -> %d .ahead files in %s%s"
      % (args.head, sum(l.startswith("END") for l in out), len(args.names), args.outdir,
         " (with CRVAL)" if args.keep_crval else ""))
