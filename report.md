# SCAMP: Kompilierung unter Linux und macOS – Bericht

Stand: 17.11.2026. Die Linux-Arbeit lief im Branch `compile-test` (16 Commits auf `72b7e76`),
der per Fast-Forward nach `master` übernommen wurde. Ein weiterer Commit (macOS-Datum,
Shebangs der Tests und dieser Bericht) folgte direkt auf `master`.
Die macOS-Arbeit lief im Branch `mac-compile` (siehe Abschnitt 6).

## 1. Was geändert wurde

### Build-System (configure.ac, m4/)

| Commit | Änderung |
|---|---|
| `e3b4310`, `73c9695` | **OpenBLAS:** Header werden auch in Unterverzeichnissen wie `openblas-pthread/` gefunden (über pkg-config). LAPACKe wird auch als separate Bibliothek (`liblapacke`) erkannt. `openblas_set_num_threads()` wird unabhängig vom Bibliotheksnamen genutzt. |
| `7be1e5a` | **MKL mit GCC** auf x86_64 Linux: GNU-Interface (`mkl_gf_*`, `mkl_gnu_thread`). Findet die Distributions-MKL auch ohne `MKLROOT`. Link-Test; Fehler werden gemeldet statt eines stummen Abbruchs. |
| `090f135`, `ec33ce5` | **MKL mit Intel-Compiler (icx/icc):** findet MKL mit und ohne `MKLROOT`, sowohl in `lib/intel64` als auch in `lib/`. Explizite Bibliotheken statt zusätzlichem `-qmkl`. Link-Test. Behoben: `-end-group`-Tippfehler und `-qmkl-ilp64` im LP64-Zweig (Linux und macOS). |
| `c0dab4d` | **ATLAS:** Header-Suche ohne autoconf-Warnungen, echter Kompiliertest von `clapack.h`, verständliche Fehlermeldung bei falschem `cblas.h`. Behoben: `test ==`, `--with-atlas-incdir`, fehlende Zusatzbibliotheken in `ATLAS_LIBS`. |
| `ad61936` | Alle `--enable-*`/`--disable-*`-Optionen werden korrekt ausgewertet. Der Intel-Compiler wird zentral aus `CC` erkannt. |
| `502826c` | **Profiling:** `-pg` für alle Compiler; `--enable-best-link` wird im Profiling-Modus vor der Bibliothekserkennung abgeschaltet. |
| `e35f00e` | `AX_PTHREAD` statt des veralteten `ACX_PTHREAD`. Klarer Fehler, wenn keine POSIX-Threads vorhanden sind. |
| `e4105b4` | Doppelte `sinclude`-Zeilen entfernt. |
| `07e1023` | `doc/src/conf.py` wird nicht mehr von `configure` erzeugt, sondern liest die Version aus `configure.ac`. Die Doku baut wieder mit Python 3 und aktuellem Sphinx (8.x). |
| (auf `master`) | Datumsangaben für die Paket-Changelogs ohne `date -R` (das BSD/macOS-`date` nicht kennt) und mit `LC_ALL=C`, also unabhängig von der Locale. |

### Quellcode

| Commit | Änderung |
|---|---|
| `d4f0715` | `field.c`: Kein Lesen über das Pufferende hinaus bei `LDAC_IMHEAD`-Headern ohne (oder mit NUL-aufgefülltem) END. |
| `aee9dd9` | `fitswrite.c`: leeres printf-Format. `fitstab.c`: Segment-Nummerierung in `remove_tab()`. `match.c`: undefiniertes Verhalten im XOR-Tausch von `flipimage()`. `prefs.h`: Enum-Typ für `cplot_device`. |
| `ae6acd6` | **Pan-STARRS1:** Der Qualitätsfilter (`QF_OBJ_GOOD`) wirkt jetzt. Vorher war er wegen falscher Operator-Rangfolge wirkungslos. ⚠ Das verringert die Zahl der Referenzsterne. |
| `9003982` | **Tycho-2, IGSL, PS1:** Die umgedrehte Behandlung der Magnitudenfehler ist korrigiert. ⚠ Das ändert die photometrische Gewichtung. |

### Tests

`884b0a8`: Neuer End-to-End-Test `tests/test_synthetic01.py`, der in `make check` läuft.
- Er erzeugt synthetische Kataloge (5 Belichtungen mit Verzeichnung, Zeiger-Offsets und ZP-Offsets) samt Referenzkatalog.
- Er prüft das Ergebnis: Astrometrie-RMS < 10 mas, Zeropoints auf 0,005 mag genau.

Alle Python-Test-Skripte beginnen jetzt mit `#!/usr/bin/env python3` (vorher teils mit `/usr/bin/python3`).

## 2. Was jetzt funktioniert (getestet auf Ubuntu 22.04)

| Compiler | Bibliotheken | Linken | `make check` |
|---|---|---|---|
| gcc | OpenBLAS + FFTW | dynamisch | 6/6 |
| gcc | MKL | dynamisch | 6/6 |
| gcc | MKL | statisch (`--enable-best-link`) | 6/6 |
| gcc | ATLAS + FFTW (mit ATLAS-eigenem `cblas.h`) | dynamisch | 6/6 |
| icx 2026.2 | OpenBLAS + FFTW | dynamisch | 6/6 |
| icx 2026.2 | MKL (ohne und mit `MKLROOT`) | dynamisch | 6/6 |
| gcc | MKL + `--enable-profiling` | dynamisch | `gmon.out` und `gprof` funktionieren |

**Nicht getestet bzw. nicht testbar:**
- icx mit statisch gelinkter MKL: Es fehlt eine statische OpenMP-Laufzeit (`libiomp5.a`). `configure` meldet das korrekt.
- Die Katalogabfragen bei VizieR (PS1/Tycho-2/IGSL): Die Server waren nicht erreichbar.

## 3. Was unter Linux (Ubuntu/Debian) nötig ist

**Pakete:**
```
autoconf automake libtool pkg-config
libfftw3-dev libplplot-dev libcurl4-gnutls-dev   # bzw. libcurl4-openssl-dev
python3-numpy python3-astropy                    # für make check
```
Dazu eine der folgenden Bibliotheksvarianten:
- **OpenBLAS:** `libopenblas-dev liblapacke-dev`
- **MKL:** `intel-mkl` bzw. `libmkl-dev`
- **ATLAS:** `libatlas-base-dev`

**Bauen:**
```
./autogen.sh
./configure --enable-mkl          # oder --enable-openblas / --enable-atlas;
                                  # ohne Option: ATLAS, falls nutzbar, sonst OpenBLAS
make -j && make check
```

**Besonderheiten:**
- **`cblas.h` über update-alternatives:** Auf Debian/Ubuntu ist `cblas.h` (ebenso `libblas.so.3` und `liblapack.so.3`) eine Alternative, die je nach installierten Paketen auf MKL, OpenBLAS oder ATLAS zeigt.
  - OpenBLAS und MKL kommen damit zurecht.
  - **ATLAS** braucht das ATLAS-eigene `cblas.h`. Ohne Option weicht `configure` sonst automatisch auf OpenBLAS aus (siehe Abschnitt 5). Für ATLAS: entweder `sudo update-alternatives --config cblas.h-x86_64-linux-gnu` auf ATLAS stellen, oder `--with-atlas-incdir` auf ein Verzeichnis zeigen lassen, in dem `cblas.h` → `cblas-atlas.h` und `clapack.h` liegen.
- **Intel-Compiler aus conda** (`dpcpp_linux-64`): icx sucht dann nur im conda-Sysroot und findet die System-Bibliotheken nicht. Abhilfe:
  ```
  ./configure CC="icx --sysroot=/" --enable-mkl
  ```
  `--enable-icx` setzt fest `CC=icx` und lässt sich deshalb hier nicht verwenden.
- **`CC` aus der conda-Umgebung:** Das Aktivieren der conda-Umgebung setzt `CC=icx`. Für einen GCC-Build muss man dann `CC=gcc` explizit angeben.
- **Statisches Linken mit icx** braucht eine vollständige oneAPI-Installation (mit `libiomp5.a`).
- **`doc/src/conf.py`** bleibt beim Konfigurieren unverändert (früher wurde es bei jedem `configure` überschrieben).

## 4. Mögliche Baustellen

### Andere Linux-Distributionen

- **Fedora/RHEL/Rocky/Alma:**
  - OpenBLAS gibt es in mehreren Varianten (`openblas`, `openblasp` = pthreads, `openblaso` = OpenMP). Das Makro sucht `openblasp` und `openblas`, aber nicht `openblaso`.
  - Die Header liegen in `/usr/include/openblas/`, das wird gefunden. Ob LAPACKe dort in libopenblas enthalten ist, ist ungetestet.
  - ATLAS liegt in `/usr/lib64/atlas` mit `libsatlas`/`libtatlas`. Diese Pfade sind im Makro vorgesehen, aber ungetestet.
  - FFTW-Header und -Bibliotheken kommen aus `fftw-devel`. Die Threads-Bibliothek `fftw3f_threads` muss vorhanden sein.
  - PLplot (`plplot-devel`) kann je nach Version per pkg-config `plplot` oder `plplotd` heißen; beides wird geprüft.
- **MKL über die oneAPI-Repos von Intel:** Libraries in `$MKLROOT/lib` (neueres Layout) oder `lib/intel64`. Beides wird unterstützt, aber nur mit Symlinks nachgestellt getestet. Wichtig: vorher `source /opt/intel/oneapi/setvars.sh`, damit `MKLROOT` gesetzt ist.
- **Arch Linux:** `openblas` enthält `cblas`; `lapacke` gibt es als separates Paket. Das sollte über den LAPACKe-Fallback funktionieren, ist aber ungetestet.
- **Alpine/musl:**
  - `error_at_line` und `mallopt` werden per configure geprüft.
  - MKL gibt es dort nicht.
  - Ob der Code sonst noch glibc-spezifische Funktionen nutzt, ist nicht untersucht.
- **Nicht-x86_64 (aarch64, ppc64le):** Nur OpenBLAS und ATLAS kommen infrage, MKL nicht. Der GCC-MKL-Zweig verweigert andere Architekturen ausdrücklich.
- **Allgemein:**
  - Statisches Linken (`--enable-best-link`) setzt voraus, dass die `.a`-Dateien installiert sind. Viele Distributionen liefern sie nicht mit.
  - `make check` erfordert numpy und astropy für das erste `python3` im `PATH`. Das ist zu beachten, wenn eine aktivierte conda- oder venv-Umgebung ein eigenes Python mitbringt.

### macOS

Siehe Abschnitt 6.

### Im Code, plattformunabhängig

- **VizieR-Abfragen:** SCAMP fragt per `http://` an. Mehrere Spiegel waren beim Test nicht erreichbar oder lieferten leere Tabellen. Es lohnt sich, die Standard-Server (`REF_SERVER`) und die Umstellung auf `https://` zu prüfen.
- **Compiler-Warnungen:** Mit maximalen Warnstufen untersucht; die echten Probleme sind behoben, siehe Abschnitt 6. Übrig sind vor allem ungenutzte Variablen und nur theoretische `sprintf`-Überläufe (z. B. `xml.c:214`, `astrefcat.c:304`).
- **Dokumentation:** Sphinx meldet noch 10 inhaltliche Warnungen, darunter das undefinierte Label `param_checkplot` und fehlende Leerzeilen in `Using.rst` und `Output.rst`.

## 5. Nachtrag: Branch `install-fix` – stabiles `./configure` ohne Optionen

**Problem:** Ein `./configure` ohne Optionen brach mit dem ATLAS-Fehler ab, sobald `cblas.h`
(Debian-Alternative) nicht auf ATLAS zeigte. Auf dem Testrechner zeigt es auf MKL
(`/usr/include/mkl/mkl_cblas.h`). Ohne Option war ATLAS aber fest gesetzt.

**Lösung:**
- **Neue Option `--enable-atlas`.** `--enable-atlas` und `--enable-openblas` stehen jetzt
  standardmäßig auf `auto`.
- **Automatik:** Erst wird ATLAS versucht. Ist ATLAS nicht nutzbar, wird OpenBLAS (mit LAPACKe)
  genommen. `configure` meldet die Wahl („checking for the linear algebra library... OpenBLAS").
- **Explizite Wahl wird strikt eingehalten:** Mit `--enable-atlas`, `--enable-openblas`,
  `--with-atlas-*dir` oder `--with-openblas-*dir` gibt es keinen Fallback, sondern den bisherigen
  klaren Fehler. Beide `--enable` gleichzeitig ergeben einen Fehler.
- **Wenn gar nichts geht:** Die Fehlermeldung nennt die Ursache für ATLAS und für OpenBLAS und
  verweist auf `--enable-mkl`.
- MKL wird in der Automatik bewusst nicht versucht. Es ersetzt auch FFTW und braucht eine eigene
  Compilerwahl.
- **`Makefile.am`:** `config/*.ahead` steht jetzt als explizite Dateiliste da. Der Wildcard
  verhinderte Builds außerhalb des Quellverzeichnisses („No rule to make target
  'config/*.ahead'").

**Getestet (gcc, Ubuntu 22.04, frischer Klon + `./autogen.sh`):**

| Aufruf | Ergebnis |
|---|---|
| `./configure` | OpenBLAS (ATLAS-`cblas.h` nicht aktiv), `make check` 6/6 |
| `./configure --with-atlas-incdir=<shim>` | ATLAS, `make check` 6/6 |
| `--enable-openblas`, `--disable-atlas` | OpenBLAS |
| `--enable-atlas` | Fehler (wie bisher, mit Hinweis auf update-alternatives) |
| `--enable-atlas --enable-openblas` | Fehler: schließen sich aus |
| `--disable-openblas` | Fehler: keine Bibliothek (ATLAS nicht nutzbar, OpenBLAS abgeschaltet) |
| `--enable-mkl` | MKL, unverändert |

**Noch offen:** `make check` außerhalb des Quellverzeichnisses (VPATH) schlägt fehl. Die Tests
suchen ihre Daten relativ zum Arbeitsverzeichnis. Das Problem bestand schon vorher und hängt
nicht mit der BLAS-Wahl zusammen.
## 6. macOS (Branch `mac-compile`)

### Geänderte Dateien

| Commit | Änderung |
|---|---|
| `d965fb9` | **Build-System:** FFTW holt Include- und Bibliothekspfade über pkg-config (`fftw3f`/`fftw3`), wenn keine Pfade angegeben sind. Unter Linux liefert pkg-config für Systempfade nichts, dort ändert sich also nichts. Behoben: falsches Quoting von `FFTW_H` bei `--with-fftw-libdir`. **OpenBLAS:** Das „keg-only“-OpenBLAS von Homebrew wird über `PKG_CONFIG_PATH` gefunden; den Bibliothekspfad aus pkg-config nutzt das Makro nur als letzten Ausweg. Mit der automatischen Bibliothekswahl aus Abschnitt 5 weicht ein `./configure` ohne Optionen auf dem Mac damit auf das OpenBLAS von Homebrew aus, weil ATLAS fehlt. **cURL:** pkg-config wird vor `curl-config` gefragt. |
| `aa2d75b` | `chealpixstore.c`: `int64_t` statt `long` beim `realloc` und `PRId64` beim Ausgeben. Auf macOS ist `int64_t` `long long`. |
| `0a6c25a` | **Tests:** `test_chealpixstore` linkt `libfits.a`, das `error()` bereitstellt. Unter Linux wurde nur zufällig die gleichnamige, aber andere glibc-Funktion `error()` verwendet. `test_chealpix` liest `int64_t` mit `SCNd64`. Die Crossid-Tests vergleichen mit `fabs()` statt `abs()`. `abs()` schnitt die Differenzen auf ganze Zahlen ab, die Prüfung war daher wirkungslos (auch unter Linux). Der Moving-Test verschiebt die Felder absichtlich um bis zu 0,3″ und prüft jetzt mit 0,5″ Toleranz statt `FLT_EPSILON`. |

### Getestet

| System | Compiler | Bibliotheken (Homebrew) | `make check` |
|---|---|---|---|
| macOS 26.6, Apple Silicon (arm64) | Apple clang 17 | OpenBLAS 0.3.34, FFTW 3.3.11, PLplot 5.15.0, System-libcurl | 6/6, keine Compiler-Warnungen |

- Check-Plots über PLplot (PNG) funktionieren, auch mit der Standard-Kantenglättung über `convert` (ImageMagick 7.1).
- Auch die bisherigen Optionen mit expliziten Pfaden (`--with-openblas-*`, `--with-fftw-*`, `--with-curl-*`) funktionieren weiterhin.
- Intel-Macs sind nicht getestet. Dort sollte derselbe Weg funktionieren, Homebrew liegt dann aber unter `/usr/local`.

### Was unter macOS nötig ist

**Pakete:**
- Xcode bzw. die Command Line Tools: `xcode-select --install`.
- Über Homebrew:
  ```
  brew install autoconf automake libtool pkg-config fftw openblas plplot
  brew install imagemagick        # optional, für CHECKPLOT_ANTIALIAS Y
  ```
- Für `make check` braucht das erste `python3` im `PATH` numpy und astropy.

**Bauen:**
```
./autogen.sh
./configure
make -j && make check
```
Es sind keine Optionen nötig. Mit `--disable-plplot` lässt sich PLplot weglassen; es bringt viele Abhängigkeiten mit (cairo, pango, gcc …).

### Besonderheiten

- **Homebrew-Pfade:** clang durchsucht `/opt/homebrew/include` und `/opt/homebrew/lib` nicht von selbst. Die Makros holen die Pfade deshalb über pkg-config.
- **Anaconda und curl:** Steht Anaconda im `PATH`, findet man dessen `curl-config` vor `/usr/bin/curl-config`. Früher wurde dann gegen das libcurl von Anaconda gelinkt, und das Programm brach beim Start mit `Library not loaded: @rpath/libcurl.4.dylib` ab. Jetzt kommt das System-libcurl über pkg-config.
- **Versionsabhängige Pfade:** pkg-config liefert die versionierten Cellar-Pfade (z. B. `/opt/homebrew/Cellar/fftw/3.3.11`). Ein `brew upgrade` zwischen `configure` und `make` erfordert ein neues `configure`. Das fertige Binary verweist dagegen auf die stabilen `/opt/homebrew/opt/...`-Pfade.
- **`libtoolize`:** `autogen.sh` meldet, `libtoolize` sei nicht verfügbar, nimmt dann aber `glibtoolize`. Die Warnung ist harmlos.
- **MKL:** Auf Apple Silicon gibt es keine MKL. Auf Intel-Macs bräuchte man den Intel-Compiler, den es für macOS nicht mehr gibt. Der MKL-Zweig des Makros ist auf macOS daher ungetestet.
- **ATLAS:** Bei Homebrew nicht verfügbar.
- **Accelerate:** Apples Accelerate-Framework (BLAS/LAPACK, aber kein LAPACKe) wird nicht unterstützt.

### Offen

- Nach den Änderungen am Build-System muss noch einmal unter Linux (Ubuntu) `make check` laufen, bevor `mac-compile` nach `master` geht.
- Die VizieR-Abfragen scheitern auch auf dem Mac (`Connection timeout for vizier.unistra.fr`), siehe Abschnitt 4.

## 6. Analyse mit maximalen Compiler-Warnstufen (Branch `mac-compile`)

### Vorgehen

Drei Builds wurden ausgewertet:

| Compiler | Optionen | Warnungen |
|---|---|---|
| Apple clang 17 | `-Wall -Wextra -Wformat=2 -Wshadow -Wcast-qual -Wconditional-uninitialized -Wunreachable-code -Wshorten-64-to-32` u. a. | 623 |
| GCC 16 (Homebrew, `gcc-16`) | `-Wall -Wextra -Wformat-overflow=2 -Wformat-truncation=2 -Wstringop-overflow=4 -Wmaybe-uninitialized -Wnull-dereference -Wduplicated-cond -Wlogical-op` u. a. | 493 |
| Apple clang 17 | `-Weverything` (nur als Statistik) | 1995 |

Über 90 % der Meldungen sind harmlos, z. B.:
- nicht initialisierte Struct-Felder (190),
- ungenutzte Variablen (~150),
- `float`→`double`-Umwandlungen,
- `%ld` für `size_t` in den Speicher-Makros (321 bei `-Weverything`),
- unbekannte Intel-Pragmas.

### Behobene Probleme

| Commit | Stelle | Problem |
|---|---|---|
| `a9f968d` | `samples.c` | **Echter Fehler:** Ist `SPREAD_MODEL` oder `SPREADERR_MODEL` im Katalog vom Typ `double`, blieb der `float`-Zeiger uninitialisiert, wurde aber zuerst geprüft und dereferenziert. Folge: Müllwerte oder Absturz. |
| `ef0cbcc` | `cplot.c:129` | **Pufferüberlauf:** Der `convert`-Befehl für die Kantenglättung (Dateiname zweimal) wurde in einen 512-Byte-Puffer geschrieben. Jetzt `snprintf`, Dateinamen in Anführungszeichen und eine Warnung, wenn der Befehl zu lang ist. |
| `ef0cbcc` | `makeit.c:209` | **Pufferüberlauf:** `OUTREF_PATH` plus Katalogname. Jetzt `snprintf` und eine Fehlermeldung, wenn der Name zu lang ist. |
| `ef0cbcc` | `fitswcs.c:388` | Ein `CUNIT` ab 32 Zeichen wurde ohne Endnull kopiert. |
| `4deef35` | `fft.c:304` | Undefiniertes Verhalten durch einen XOR-Tausch (gleiches Muster wie früher in `match.c`). |
| `4deef35` | `astrsolve.c:1634` | Undefiniertes Verhalten durch `x[i] = x[i] = BIG;`. |
| `4deef35` | `astrsolve.c:251/258`, `astrcplot.c:4965/5230` | Zugriff über eine Schleifenvariable, die nur zufällig den richtigen Wert hat. |
| `4deef35` | `catout.c:271` | Irreführende Einrückung. |

### Geprüft, aber unkritisch

- **Restliche Meldungen zu „möglicherweise uninitialisiert“:** Die Kontrollfluss-Analyse greift zu kurz, z. B. bei Schleifen, die mindestens einmal laufen, oder bei `error()`, das das Programm beendet.
- **Format-Strings, die keine Literale sind (26):** Sie stammen aus internen Tabellen, nicht aus Benutzereingaben.
- **`sprintf`-Meldungen zu Datum und Zahlenwerten:** Ein Überlauf tritt nur bei unrealistischen Werten auf.
- **`strncpy` ohne Endnull:** Betrifft FITS-Felder fester Breite (8 bzw. 80 Zeichen) und ist so gewollt.
- **Verkürzungen von 64 auf 32 Bit:** In HEALPix, beim FITS-I/O in Blöcken und im curl-Puffer bleiben die Werte klein.
- **`copy_wcs(NULL)`** würde abstürzen, aber kein Aufrufer übergibt `NULL`.
- **Leerzeichen in `CHECKPLOT_NAME`** sind ohnehin nicht möglich, weil SCAMP Konfigurationswerte an Leerzeichen trennt.

Nach den Korrekturen besteht `make check` weiterhin 6/6. Der Standard-Build mit clang ist warnungsfrei, und die Check-Plots mit Kantenglättung funktionieren weiterhin.

### So wiederholen

```
./configure CC=gcc-16 CFLAGS="-g -O2 -Wall -Wextra -Wformat-overflow=2 \
  -Wformat-truncation=2 -Wstringop-overflow=4 -Wmaybe-uninitialized"
make -k 2>&1 | grep "warning:" | sort -u
```
