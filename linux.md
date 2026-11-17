# macOS-Änderungen unter Linux (Ubuntu) testen

Ziel: Prüfen, dass die macOS-Änderungen (Build-System: FFTW, OpenBLAS und
cURL über pkg-config; Korrekturen aus der Warnungsanalyse) unter Linux nichts
verändern und dass alle Tests weiterhin bestehen. Die Änderungen sind auf
`master` (auf den Commit „Make plain ./configure work“ aufgesetzt).

## 1. Stand holen

```
cd ~/git/scamp            # bzw. dein Pfad zum Repository
git status                # sollte sauber sein
git checkout master
git pull
git log --oneline -12     # u. a. "Find Homebrew libraries on macOS ..."
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

## 5. Ohne Option (automatische Wahl: ATLAS, sonst OpenBLAS)

```
make distclean
./configure 2>&1 | tee configure-auto.log
make -j && make check
grep -E "linear algebra library|cURL pkg-config|cmdline" configure-auto.log
grep -E "^# (TOTAL|PASS|FAIL)" tests/test-suite.log
```

Erwartet:
- `checking for the linear algebra library... ATLAS` oder `... OpenBLAS`, je
  nachdem, worauf die `cblas.h`-Alternative zeigt (siehe report.md, Abschnitt 5).
- 6 von 6 bestanden.

Optional, mit ATLAS erzwungen (braucht das ATLAS-eigene `cblas.h`, siehe
report.md, Abschnitt 3):

```
make distclean
./configure --with-atlas-incdir=<Verzeichnis> && make -j && make check
```

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
