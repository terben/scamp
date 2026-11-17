# Branch `mac-compile` unter Linux (Ubuntu) testen

Ziel: Prüfen, dass die macOS-Änderungen am Build-System (FFTW, OpenBLAS und
cURL über pkg-config) unter Linux nichts verändern und dass alle Tests
weiterhin bestehen.

## 1. Branch holen

Voraussetzung: Der Branch `mac-compile` wurde vom Mac aus gepusht
(`git push -u origin mac-compile`).

```
cd ~/git/scamp            # bzw. dein Pfad zum Repository
git status                # sollte sauber sein
git fetch origin
git checkout mac-compile
git log --oneline -5      # oberster Commit: "Add a macOS section to the build report"
```

Wenn eine conda-Umgebung aktiv ist, die `CC=icx` setzt, für die GCC-Builds
`CC=gcc` angeben (siehe report.md, Abschnitt 3) oder vorher `conda deactivate`.

## 2. Build-System neu erzeugen

```
make distclean 2>/dev/null
./autogen.sh
```

## 3. OpenBLAS

```
./configure --enable-openblas 2>&1 | tee configure-openblas.log
make -j && make check
```

Prüfen:

```
grep -E "cURL pkg-config|LAPACKE_dpotrf|cmdline" configure-openblas.log
grep -E "^# (TOTAL|PASS|FAIL)" tests/test-suite.log
```

Erwartet:
- `checking for cURL pkg-config info... yes`
- Die Link-Zeile enthält `-lcurl` und, wie bisher, keine zusätzlichen `-L`-Pfade für FFTW.
- Die Compile-Zeile enthält keine zusätzlichen `-I`-Pfade für FFTW.
- `make check`: 6 von 6 bestanden.

## 4. MKL

```
make distclean
./configure --enable-mkl 2>&1 | tee configure-mkl.log
make -j && make check
grep -E "cURL pkg-config|cmdline" configure-mkl.log
grep -E "^# (TOTAL|PASS|FAIL)" tests/test-suite.log
```

Erwartet: 6 von 6 bestanden.

## 5. ATLAS (Standard ohne Option)

Wie bisher braucht ATLAS das ATLAS-eigene `cblas.h` (siehe report.md,
Abschnitt 3: `update-alternatives` oder `--with-atlas-incdir`).

```
make distclean
./configure 2>&1 | tee configure-atlas.log
make -j && make check
grep -E "OpenBLAS is enabled|cURL pkg-config|cmdline" configure-atlas.log
grep -E "^# (TOTAL|PASS|FAIL)" tests/test-suite.log
```

Erwartet:
- `checking whether OpenBLAS is enabled... no`: Unter Linux bleibt ATLAS der Standard.
- 6 von 6 bestanden.

## 6. Optional: Intel-Compiler

```
make distclean
./configure CC="icx --sysroot=/" --enable-mkl 2>&1 | tee configure-icx.log
make -j && make check
grep -E "^# (TOTAL|PASS|FAIL)" tests/test-suite.log
```

## 7. Bei Fehlern

Bitte Folgendes mitbringen bzw. einfügen:

```
tail -50 config.log
cat tests/test-suite.log
```

## 8. Aufräumen

```
make distclean
rm -f configure-*.log
git status                # sollte sauber sein
```
