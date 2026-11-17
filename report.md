# SCAMP: Kompilierung unter Linux und macOS (mit Ausblick auf Windows) – Bericht

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
- **Compiler-Warnungen:** Mit maximalen Warnstufen untersucht; die echten Probleme sind behoben, siehe Abschnitt 7. Übrig sind vor allem ungenutzte Variablen und nur theoretische `sprintf`-Überläufe (z. B. `xml.c:214`, `astrefcat.c:304`).
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
| `c3ca0bf` | **Build-System:** FFTW holt Include- und Bibliothekspfade über pkg-config (`fftw3f`/`fftw3`), wenn keine Pfade angegeben sind. Unter Linux liefert pkg-config für Systempfade nichts, dort ändert sich also nichts. Behoben: falsches Quoting von `FFTW_H` bei `--with-fftw-libdir`. **OpenBLAS:** Das „keg-only“-OpenBLAS von Homebrew wird über `PKG_CONFIG_PATH` gefunden; den Bibliothekspfad aus pkg-config nutzt das Makro nur als letzten Ausweg. Mit der automatischen Bibliothekswahl aus Abschnitt 5 weicht ein `./configure` ohne Optionen auf dem Mac damit auf das OpenBLAS von Homebrew aus, weil ATLAS fehlt. **cURL:** pkg-config wird vor `curl-config` gefragt. |
| `b4409f7` | `chealpixstore.c`: `int64_t` statt `long` beim `realloc` und `PRId64` beim Ausgeben. Auf macOS ist `int64_t` `long long`. |
| `4e1dcb5` | **Tests:** `test_chealpixstore` linkt `libfits.a`, das `error()` bereitstellt. Unter Linux wurde nur zufällig die gleichnamige, aber andere glibc-Funktion `error()` verwendet. `test_chealpix` liest `int64_t` mit `SCNd64`. Die Crossid-Tests vergleichen mit `fabs()` statt `abs()`. `abs()` schnitt die Differenzen auf ganze Zahlen ab, die Prüfung war daher wirkungslos (auch unter Linux). Der Moving-Test verschiebt die Felder absichtlich um bis zu 0,3″ und prüft jetzt mit 0,5″ Toleranz statt `FLT_EPSILON`. |

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

## 7. Analyse mit maximalen Compiler-Warnstufen (Branch `mac-compile`)

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
| `989f98f` | `samples.c` | **Echter Fehler:** Ist `SPREAD_MODEL` oder `SPREADERR_MODEL` im Katalog vom Typ `double`, blieb der `float`-Zeiger uninitialisiert, wurde aber zuerst geprüft und dereferenziert. Folge: Müllwerte oder Absturz. |
| `49d0fd4` | `cplot.c:129` | **Pufferüberlauf:** Der `convert`-Befehl für die Kantenglättung (Dateiname zweimal) wurde in einen 512-Byte-Puffer geschrieben. Jetzt `snprintf`, Dateinamen in Anführungszeichen und eine Warnung, wenn der Befehl zu lang ist. |
| `49d0fd4` | `makeit.c:209` | **Pufferüberlauf:** `OUTREF_PATH` plus Katalogname. Jetzt `snprintf` und eine Fehlermeldung, wenn der Name zu lang ist. |
| `49d0fd4` | `fitswcs.c:388` | Ein `CUNIT` ab 32 Zeichen wurde ohne Endnull kopiert. |
| `07b4e4b` | `fft.c:304` | Undefiniertes Verhalten durch einen XOR-Tausch (gleiches Muster wie früher in `match.c`). |
| `07b4e4b` | `astrsolve.c:1634` | Undefiniertes Verhalten durch `x[i] = x[i] = BIG;`. |
| `07b4e4b` | `astrsolve.c:251/258`, `astrcplot.c:4965/5230` | Zugriff über eine Schleifenvariable, die nur zufällig den richtigen Wert hat. |
| `07b4e4b` | `catout.c:271` | Irreführende Einrückung. |

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

## 8. Windows: Einschätzung zu Cygwin (nicht getestet)

Stand: 17.11.2026. Es gab keinen Build-Versuch. Die Einschätzung beruht auf einer Durchsicht des Codes und auf den Paketlisten von Cygwin (x86_64).

### Kurzfassung

SCAMP ist unter Cygwin sehr wahrscheinlich installierbar, aber nicht allein mit Cygwin-Paketen:
- Der **Code** ist unkritisch.
- Das Hindernis ist die **Linear-Algebra-Bibliothek**. SCAMP braucht LAPACKe (oder das `clapack.h` von ATLAS), und Cygwin liefert beides nicht.
- Der realistische Weg ist, **OpenBLAS selbst zu bauen**, denn OpenBLAS enthält LAPACKe.
- Für Windows-Nutzer ist **WSL2** (Ubuntu unter Windows) deutlich einfacher; dort gilt Abschnitt 3 unverändert.

### Code

- **Nur POSIX:** SCAMP verwendet nur Schnittstellen, die Cygwin nachbildet: `pthread` (nur Mutex und Condition-Variablen), `mmap`/`munmap`, `popen`/`system`, `signal`, `dlfcn.h` und `sysconf(_SC_NPROCESSORS_ONLN)`.
- **Gleiches Datenmodell wie Linux:** Cygwin auf x86_64 ist LP64, `long` hat also 64 Bit. Die Typprobleme von Windows-nativ (dort ist `long` 32 Bit) entstehen deshalb nicht.
- **glibc-Eigenheiten sind abgesichert:** `mallopt` und `malloc.h` stehen hinter `HAVE_MALLOPT`, `error_at_line` wird nicht verwendet. Der Testfehler, bei dem zufällig `error()` aus der glibc genommen wurde, ist behoben (`4e1dcb5`); Cygwin nutzt newlib statt glibc.
- **Dateien:** FITS-Dateien werden mit `"rb"`/`"wb"` geöffnet, also im Binärmodus.
- `url.c` hat einen Zweig `#ifdef _WIN32`. Den definiert der GCC von Cygwin nicht, es gilt also der POSIX-Zweig.

### Abhängigkeiten

| Bibliothek | Cygwin-Paket | Bewertung |
|---|---|---|
| FFTW 3 (float, threads) | `libfftw3-devel` 3.3.11 (enthält `cygfftw3f_threads-3.dll`) | vorhanden |
| cURL | `libcurl-devel` | vorhanden |
| BLAS/cblas | `liblapack-devel` 3.12: `cblas.h`, `libblas`, `liblapack`. OpenBLAS gibt es nur als Laufzeitersatz für diese DLLs, ohne Devel-Paket. | vorhanden, reicht aber nicht |
| **LAPACKe** | **nicht vorhanden:** `liblapack-devel` enthält weder `lapacke.h` noch `liblapacke` | **fehlt** |
| ATLAS (`clapack.h`) | nicht vorhanden | fehlt |
| MKL | nicht für Cygwin | fehlt |
| PLplot | kein Paket | selbst bauen oder `--disable-plplot` |
| numpy, astropy (für `make check`) | numpy als `python3x-numpy` (Name je nach Python-Version); astropy nicht als Paket | astropy per `pip`, kompiliert C-Erweiterungen |

SCAMP nutzt aus LAPACKe `LAPACKE_dposv`, `_dpotrf`, `_dpotri`, `_dpotrs`, `_dgesv`, `_dppsv`, `_dspsv` und `_dsysv`. Ohne LAPACKe oder ATLAS lässt es sich nicht linken. MKL ist die dritte Alternative, gibt es aber unter Cygwin nicht.

### Vorgeschlagener Weg (ungetestet)

1. **Cygwin-Pakete installieren:**
   `gcc-core gcc-fortran make git autoconf automake libtool pkg-config libfftw3-devel libcurl-devel python3 python3x-numpy`. Für `make check` zusätzlich `pip install astropy`.
2. **OpenBLAS mit LAPACKe aus dem Quellcode bauen:**
   ```
   git clone https://github.com/OpenMathLib/OpenBLAS.git
   cd OpenBLAS
   make -j USE_THREAD=1
   make PREFIX=/usr/local install
   ```
3. **SCAMP bauen:**
   ```
   export PKG_CONFIG_PATH=/usr/local/lib/pkgconfig
   ./autogen.sh
   ./configure --disable-plplot
   make -j && make check
   ```
   - Ohne Optionen sollte die automatische Wahl (Abschnitt 5) ATLAS verwerfen und das selbst gebaute OpenBLAS nehmen. Für ATLAS fehlt `clapack.h`; das `cblas.h` aus `liblapack-devel` stört nicht, weil das Makro OpenBLAS am Eintrag `openblas_set_num_threads` erkennt.
   - Falls das nicht klappt, die Pfade explizit angeben:
     `--with-openblas-incdir=/usr/local/include --with-openblas-libdir=/usr/local/lib`.
4. **Zur Laufzeit** muss die OpenBLAS-DLL über den `PATH` auffindbar sein, z. B. `/usr/local/bin`. Prüfen mit `ldd src/scamp.exe`.

### Mögliche Stolpersteine

- **Namen von Bibliotheken und Importbibliotheken:** Unter Cygwin linkt man über `lib*.dll.a`, zur Laufzeit werden `cyg*.dll` geladen. Es ist zu prüfen, ob `AC_SEARCH_LIBS` mit dem selbst gebauten OpenBLAS sofort funktioniert.
- **libtool unter Cygwin** baut nur die internen statischen Bibliotheken (`libfits.a`, `libwcs_c.a`), das sollte unkritisch sein. Das Programm heißt `scamp.exe`; die Tests in `make check` müssen damit zurechtkommen. Die Python-Tests rufen `scamp` auf, und Cygwin findet `.exe` in der Regel auch ohne Endung.
- **Leistung:** Threads und `mmap` sind unter Cygwin emuliert und langsamer als unter Linux. Für große Datenmengen ist WSL2 vorzuziehen.
- **Ohne `--disable-plplot`** müsste PLplot selbst gebaut werden; das PLplot-Wiki beschreibt den Bau unter Cygwin.

### Alternative: WSL2

WSL2 unter Windows 10/11 bringt ein echtes Ubuntu mit. Dort funktionieren die Anleitung aus Abschnitt 3, alle Pakete (inklusive PLplot, astropy und MKL) und `make check` ohne Änderungen. Für Windows-Nutzer ist das der empfohlene Weg.

### Testmöglichkeit

Ein Cygwin-Build ließe sich ohne eigenen Windows-Rechner über GitHub Actions prüfen: Windows-Runner und die Action `cygwin/cygwin-install-action`, mit den Schritten 1–3 von oben. Das ist bisher nicht umgesetzt.

### Quellen

- Cygwin-Paket `liblapack-devel`: https://cygwin.com/packages/summary/liblapack-devel.html (Dateiliste: https://cygwin.com/packages/x86_64/liblapack-devel/liblapack-devel-3.12.0-1)
- Cygwin-Paket `libfftw3-devel`: https://cygwin.com/packages/summary/libfftw3-devel.html (Dateiliste `libfftw3_3`: https://cygwin.com/packages/x86_64/libfftw3_3/libfftw3_3-3.3.11-1)
- OpenBLAS unter Cygwin nur als Laufzeitersatz: https://sourceware.org/pipermail/cygwin-announce/2023-February/010968.html und https://sourceware.org/pipermail/cygwin/2020-April/244676.html
- PLplot unter Cygwin: https://sourceforge.net/p/plplot/wiki/Setup_cygwin/

## 9. Warnungsanalyse unter Linux mit gcc und icx (Branch `robust_code`)

Stand: 17.11.2026. Diese Analyse ergänzt Abschnitt 7 (macOS, clang/GCC 16) um gcc 11 und icx 2026.2 unter Ubuntu 22.04. Dazu kommt ein Laufzeittest mit AddressSanitizer und UBSan. Gebaut wurde jeweils in einer Kopie des Stands `b953075` mit `--enable-mkl`.

### Vorgehen

| Build | Optionen | Warnungen |
|---|---|---|
| gcc 11.4 | `-Wall -Wextra -Wformat=2 -Wformat-overflow=2 -Wformat-truncation=2 -Wstringop-overflow=4 -Wnull-dereference -Wduplicated-cond -Wduplicated-branches -Wlogical-op -Wshadow -Wcast-qual -Wconversion -Warray-bounds=2 -Wrestrict -Wswitch-enum -Wfloat-equal` u. a., dazu `-fanalyzer` | 1300 |
| icx 2026.2 | `-Wall -Wextra -Wformat=2 -Wconditional-uninitialized -Wsometimes-uninitialized -Wunreachable-code -Wshorten-64-to-32 -Wcomma -Wloop-analysis -Wfortify-source` u. a. | 580 |
| gcc 11.4, `-O1 -fsanitize=address,undefined` | `make check` und gezielte Testläufe | 4 Laufzeitfehler (s. u.) |

Wie in Abschnitt 7 ist der Großteil harmlos. Das betrifft vor allem:
- `float`/`double`-Umwandlungen (`-Wconversion`, `-Wfloat-conversion`, ~350),
- nicht initialisierte Struct-Felder (`-Wmissing-field-initializers`, ~190),
- Gleichheitsvergleiche von Gleitkommazahlen (190),
- ungenutzte Variablen (~150),
- 64→32-Bit-Verkürzungen (63, gleiche Stellen wie in Abschnitt 7),
- Speicherlecks laut `-fanalyzer` (66). Fast alle liegen auf Pfaden, die mit `error()` enden.

### Echte Fehler (bestätigt und behoben)

| Stelle | Hinweis durch | Problem | Nachweis |
|---|---|---|---|
| `preflist.h:145,211` / `prefs.h:74-76` (ebenso `ASTR_FLAGSMASK`, `PHOT_FLAGSMASK`) | UBSan (misaligned store) | `FLAGS_MASK` und `WEIGHTFLAGS_MASK` sind `P_INT`, die Felder aber `unsigned short`. `readprefs()` schreibt 4 Byte in ein 2-Byte-Feld. **Folge 1:** `WEIGHTFLAGS_MASK` überschreibt die unteren 16 Bit von `IMAFLAGS_MASK`, wenn es danach gelesen wird (z. B. auf der Kommandozeile). **Folge 2:** Im XML steht `Flags_Mask` falsch. **Folge 3:** Auf Big-Endian-Systemen wären die Masken immer 0. | Mit `IMAFLAGS_MASK 0x10001` in der Konfiguration und `-WEIGHTFLAGS_MASK 0xff` ergibt sich `ImaFlags_Mask = 65536`. Mit den Standardwerten steht im XML `Flags_Mask = 16711920` (0x00FF00F0) statt 240. |
| `astrefcat.c:1474-1554` (`read_astrefsamples`, Referenzkatalog aus Datei) | gcc `-Wmaybe-uninitialized`, icx `-Wconditional-uninitialized` | `dobsdate`/`obsdate` werden nicht mit `NULL` vorbelegt (anders als die übrigen Spaltenzeiger). Ist `OBSDATE` im Katalog `float`, wird der nicht initialisierte `double`-Zeiger dereferenziert. Gleiches Muster wie der in Abschnitt 7 behobene Fehler in `samples.c`. | Referenzkatalog mit `OBSDATE` als `1E`: der ASan-Build stürzt in `astrefcat.c:1554` ab (SEGV). Der normale Build läuft nur zufällig durch. |
| `astrefcat.c:1474` | gcc `-fanalyzer` (NULL-Dereferenz) | Die Bandprüfung („enough bands“) verwendet `key` von `OBSDATE` statt von der Magnitudenspalte. Fehlt `OBSDATE` und ist `band>0`, folgt eine NULL-Dereferenz. Sonst wird die falsche Spalte geprüft. | Code-Durchsicht |
| `prefs.c:625-626` | UBSan (index -1) | `REF_NTRIES` gibt es in `preflist.h` nicht. `nref_ntries` ist also immer 0, und `ref_ntries[-1]` wird gelesen. `ref_ntries` wird nirgends benutzt (toter Code mit undefiniertem Verhalten). | Bei jedem Lauf |
| `catout.c:325-333`, `:566-574` | gcc `-fanalyzer` (file leak) | Bei `MERGEDOUTCAT_TYPE`/`FULLOUTCAT_TYPE ASCII_VOTABLE` wird die Ausgabedatei nie geschlossen. Erst `exit()` schreibt sie; bei einem späteren Absturz ist sie unvollständig. | Code-Durchsicht |
| `dgeomap.c:120` | gcc `-Wformat-overflow` | `str[64]` für „Generating differential geometry map for instrument A%d, set %d/%d“ passt nur bei einstelligen Zahlen (63 Zeichen + NUL). Mit `SAVE_DGEOMAP Y` und mindestens 10 Sets (Mosaikkameras) oder Instrumenten läuft der Stack-Puffer über. | Nachgezählt |

### Korrekturen

| Datei | Änderung |
|---|---|
| `prefs.h` | `sexflags_mask`, `wflags_mask`, `astr_sexflagsmask` und `phot_sexflagsmask` sind jetzt `unsigned int`, passend zu `P_INT`. Ein Abgleich aller `preflist.h`-Einträge mit den Feldtypen (per gdb `whatis`) fand keine weiteren Abweichungen. |
| `astrefcat.c` | `dobsdate`/`obsdate` werden mit `NULL` vorbelegt. Die Bandprüfung folgt jetzt direkt auf das Lesen der Magnitudenspalte und verwendet deren `key`. |
| `prefs.c`, `prefs.h` | Die Schleife über `ref_ntries` und die ungenutzten Felder `ref_ntries`/`nref_ntries` sind entfernt. |
| `catout.c` | Die VOTable-Ausgabe wird geschlossen, wenn sie nicht nach `stdout` geht. |
| `dgeomap.c` | Der Puffer hat jetzt `MAXCHAR` Zeichen, geschrieben wird mit `snprintf`. |
| `tests/test_crossid_single_catalog*.c` | `calloc` statt `malloc`, nach `realloc` wird der neue Bereich genullt. `fgroupstruct` wird genullt, `fopen` geprüft und die Datei geschlossen. |

**Nachgeprüft:**
- Mit `IMAFLAGS_MASK 0x10001` und `-WEIGHTFLAGS_MASK 0xff` ergibt sich `ImaFlags_Mask = 65537`, und `Flags_Mask` steht im XML mit 240.
- Der Referenzkatalog mit `float`-`OBSDATE` läuft im ASan-Build ohne Fehler.
- Die VOTable aus `MERGEDOUTCAT_TYPE ASCII_VOTABLE` ist vollständig und gültiges XML.
- `make check` ergibt 6/6 mit gcc, mit icx und mit gcc + ASan/UBSan, ohne Laufzeitmeldungen.

### Potentielle Probleme (nur bei ungewöhnlichen Eingaben, nicht behoben)

- **`prefs.c:186-193`:** Beim Einsetzen von `$VAR` in Konfigurationswerte fehlt jede Längenprüfung (`envname[512]`, `value2[MAXCHARL]`). Eine sehr lange Umgebungsvariable führt zu einem Überlauf.
- **`fitsutil.c:575-590` (`fitswrite`, `H_STRINGS`):** Ein String ab 79 Zeichen bzw. mit Hochkommas wird ohne Endnull nach `str2[81]` kopiert und überläuft dann `str[81]`. Die heutigen Aufrufer übergeben kürzere Werte (FITS-Karten).
- **`fitsutil.c:532`:** `%16.8f` für sehr große Header-Werte (> 1e60) überläuft `str[81]`.
- **`fitscat.c:140`:** `sprintf(str2, "%s …", str2, …)` mit überlappenden Puffern ist undefiniertes Verhalten. `addhistoryto_cat()` wird von SCAMP aber nicht aufgerufen.
- **`quadtree.c:135`:** Das Ergebnis von `calloc` wird nicht geprüft.
- **`prefs.c:716`:** Der Rückgabewert von `fgets` wird ignoriert; das ist hier unschädlich.

### Geprüft, aber unkritisch

- **`fgroup.c:563` (double free laut `-fanalyzer`):** Fehlalarm, die Felder werden mit `calloc` angelegt und je einmal freigegeben.
- **`chealpix.c:932` (negativer Shift):** `nside` ist in SCAMP immer eine Zweierpotenz.
- **`match.c:182/220`, `photsolve.c:207`, `proj.c`, `wcs.c` (icx: „may be uninitialized“):** Schleifen laufen mindestens einmal, bzw. die Zweige sind vollständig.
- **`astrefcat.c:233`:** `astref_ctype` ist ohne Endnull deklariert, wird aber nur mit `strncpy(…, 8)` gelesen.
- **`fitsbody.c:657`, `fitscheck.c:70`:** Vorzeichenvergleiche mit positiven Werten.
- **`fitsconv.c:120`, `fitshead.c:327`, `fitstab.c:252`:** Fehlalarme (Makro-Prüfung auf ein Array bzw. vorher abgefangene Fälle).

### Tests unter AddressSanitizer

Vor den Korrekturen ergab `make check` mit ASan/UBSan 4/6. Die beiden Crossid-Tests (`test_crossid_single_catalog*`) scheitern. Die Ursache liegt in den Tests, nicht in SCAMP: Sie legen `fieldstruct`, `setstruct` und die Samples mit `malloc` statt `calloc` an und verlassen sich darauf, dass `nextsamp`/`prevsamp` 0 sind. Mit `ASAN_OPTIONS=max_malloc_fill_size=0` bestehen beide. SCAMP selbst setzt die Samples in `malloc_samples`/`realloc_samples` korrekt auf 0. Die beiden Python-Tests liefen unter ASan ohne Speicherfehler; gemeldet wurden nur die oben genannten UBSan-Befunde in `prefs.c` und `xml.c`. Nach den Korrekturen ergibt sich 6/6 ohne Meldungen.

### So wiederholen

```
./configure CC=gcc --enable-mkl CFLAGS="-g -O2 -Wall -Wextra -Wformat=2 -Wformat-overflow=2 \
  -Wformat-truncation=2 -Wstringop-overflow=4 -Wnull-dereference -Wconversion -fanalyzer"
./configure CC="icx --sysroot=/" --enable-mkl CFLAGS="-g -O2 -Wall -Wextra -Wformat=2 \
  -Wconditional-uninitialized -Wsometimes-uninitialized -Wshorten-64-to-32 -Wunreachable-code"
./configure CC=gcc --enable-mkl CFLAGS="-g -O1 -fno-omit-frame-pointer -fsanitize=address,undefined" \
  LDFLAGS="-fsanitize=address,undefined"
ASAN_OPTIONS=detect_leaks=0 make check
```

## 10. Warnungsfreier Build mit `-Wall` (Branch `wall_clean`)

Stand: 17.11.2026. Ziel: Der Build mit `-Wall` soll ohne Warnungen durchlaufen, damit neue Warnungen sofort auffallen. Gleichzeitig sollen die Änderungen klein und thematisch getrennt bleiben, damit Upstream-Änderungen weiter übernommen werden können.

### Vorgehen

- Gebaut wurde mit `-Wall` in drei Konfigurationen: gcc + MKL; gcc + OpenBLAS; gcc + OpenBLAS ohne Threads und ohne PLplot. Entfernt wurde nur, was in **allen** Konfigurationen ungenutzt ist. Variablen, die nur mit Threads gebraucht werden, stehen jetzt unter `USE_THREADS`.
- Gegenprobe mit clang 14, icx 2026.2 (jeweils `-Wall`) und gcc mit `-fsanitize=address,undefined`.
- Jede Kategorie ist ein eigener Commit. Nach jedem Schritt lief `make check` (6/6).
- Zusätzlich ein Lauf mit Eigenbewegungen und `SAVE_DGEOMAP Y`. Die Differential-Geometry-Map ist gegenüber `master` bis auf Thread-Rauschen (≈ 4·10⁻⁹) identisch.

| Vorher (gcc 11, `-Wall`) | Nachher |
|---|---|
| 234 Warnungen | 0 (auch mit clang 14 und icx 2026.2) |

### Commits

| Commit | Inhalt |
|---|---|
| `2cffbb1` | Ungenutzte lokale Variablen und zwei ungenutzte `static`-Funktionen entfernt. |
| `d0963c9` | Variablen entfernt, die gesetzt, aber nie gelesen werden, samt Code, der nur sie berechnet hat (z. B. Pixelskalen und Beschriftungspositionen in Check-Plots, deren Verwendung upstream auskommentiert ist). |
| `96615e4` | **Fehler:** Der Check-Plot `ASTR_REFPROPER` zeigte auf beiden Achsen die gemessene Eigenbewegung und damit immer eine Diagonale. Er war seit Upstream-Commit `c394c7b` ohne Aussagekraft. Die x-Achse zeigt wieder den Referenzkatalog. |
| `5d3f006` | `-Wunknown-pragmas` für die Intel-Pragmas (`ivdep`, `nounroll`) lokal in den zwei betroffenen Dateien abgeschaltet. Eine zentrale Lösung über `configure` funktioniert mit clang nicht, weil dort ein späteres `-Wall` im `CFLAGS` gewinnt. |
| `cf423a9` | `snprintf`/`strftime`/`memcpy` statt ungeprüfter Kopien. **Fehler:** Die Fortschrittsmeldung in `astrsolve.c` lief ab 1000 Feldern pro Gruppe über (`str[64]`). In `fitswrite()` liefen String-Werte ab 79 Zeichen über. Dazu `sprintf` mit überlappenden Puffern in `fitscat.c` und eine Längenprüfung für den Namen der Swap-Datei. |
| `5774999` | „Möglicherweise uninitialisiert“: `lng`/`lat` für den Referenzkatalog in `astrsolve.c` aus dem richtigen Set. Einspaltige bzw. einzeilige Karten in `dgeomap.c` sind jetzt definiert. Sonst Zeiger-Initialisierungen bei Fehlalarmen. |
| `3ab2acb` | Rückgabewert von `system()` beim Anti-Aliasing auswerten (Warnung bei Fehler), `QMEMCPY` auf ein lokales Array, fehlende Klammern in `preflist.h`. |
| `4f0b923` | Von clang/icx und gcc `-O1` zusätzlich gemeldet: **Überlauf** beim Anhängen von `_<Gruppe>` an `MERGEDOUTCAT_NAME`, `FULLOUTCAT_NAME` und `DGEOMAP_NAME` bei sehr langen Namen; außerdem zwei Zähler, die nur hochgezählt werden. |
| (nach `cb62947`) | `invert_wcs()` ist jetzt eine leere Funktion. Die polynomiale Inversion ist upstream auskommentiert; übrig war nur eine Gitter-Abtastung mit Genauigkeitstest, deren Ergebnis verworfen wurde (im Testlauf 10 Aufrufe). Die Ergebnisse sind unverändert. |

### Offen bzw. zu entscheiden

- **Eigenbewegungskorrektur in `astrsolve.c:1661/1708` (behoben, aber nicht aktiv):** `properr2` wurde aus der Eigenbewegung selbst berechnet (`wcsprop²·wcschi2`) statt aus ihrem Fehler. Der Dämpfungsfaktor `prop²/(prop²+properr2)` wurde so zu `1/(1+χ²)`, also unabhängig von der Messgenauigkeit (bei χ² ≈ 1 wurde jede Eigenbewegung halbiert). Jetzt wird `wcsproperr²·wcschi2` verwendet, wie in `astrefcat.c:925`. Das Schlüsselwort `CORRECT_PROPERMOTIONS` war seit `c394c7b` (2013) auskommentiert (upstream weiterhin); es ist inzwischen wieder verfügbar, Standard `N`. Weitere Probleme dieser Option und ihre Behebung: siehe Abschnitt 11.
- **`photsolve.c`:** Die Koeffizienten-Arrays `*2` (Offsets pro Set, `offlag`) werden gefüllt, aber nie in die Matrix übernommen. Offenbar ist das Feature unvollständig. Es wurden nur die toten Zuweisungen entfernt.

## 11. Eigenbewegungen: `COMPUTE_PROPERMOTIONS` und `CORRECT_PROPERMOTIONS`

Stand: 17.11.2026. Untersucht mit synthetischen Mehrepochen-Daten (`tests/gen_synth_pm.py`): 8 Belichtungen von 2014 bis 2022, 20 % schnelle Sterne (σ = 60 mas/yr je Achse), Referenzkatalog mit Eigenbewegungen zur Epoche 2016. Verglichen wurden die gemessenen Eigenbewegungen und die gelösten WCS mit der Wahrheit.

### Behobene Fehler (aktiver Code)

| Stelle | Problem | Nachweis |
|---|---|---|
| `proper.c:504` | **Eigenbewegungen fehlen ohne Referenzkatalog.** Beim Mittelwert der Positionen stand `astromlabel` statt `astromlabel>=0`. Mit `INCLUDE_ASTREFCATALOG N` wurden alle Messungen des ersten astrometrischen Instruments (Label 0) übersprungen und dann ganz verworfen. Bei nur einem Instrument blieb fast jede Quelle ohne Eigenbewegung (Wert 0). Der Fehler besteht seit 2012 (`38e14f3`), auch upstream. | Test: 88 % der Quellen ohne Eigenbewegung, Steigung gemessen/wahr 0,15 statt 1. Nach der Korrektur 0 % und 0,999. |
| `astrefcat.c:1014` | Mit `ASTREFEPOCH_TYPE` ungleich `ORIGINAL` werden VizieR-Referenzpositionen auf `epoch_in` propagiert, `sample->epoch` behielt aber die Katalogepoche. Mit `INCLUDE_ASTREFCATALOG Y` ging der Referenzpunkt so zur falschen Zeit in den Eigenbewegungsfit ein. Jetzt wird `epoch_in` gesetzt. | Code-Durchsicht; mangels erreichbarer VizieR-Server nicht getestet. |

Neuer Test `tests/test_propmotion01.py` in `make check`: Er prüft bei `INCLUDE_ASTREFCATALOG Y` und `N`, dass alle Quellen eine Eigenbewegung haben, dass die robuste Streuung unter 6 mas/yr liegt und dass die Steigung für schnelle Sterne 1 ± 0,05 beträgt. Die gemeinsamen Teile der Generatoren stehen jetzt in `tests/synth_lib.py`; die Daten von `gen_synth.py` sind unverändert (byte-identisch geprüft).

### `CORRECT_PROPERMOTIONS`

Die Option war seit 2013 auskommentiert (upstream weiterhin) und unvollständig implementiert. Inzwischen ist sie wieder verfügbar (Standard `N`); siehe den Unterabschnitt „Dritter Lösungsschritt“ unten. Stand der ursprünglichen Untersuchung:

| Lauf (Testdaten oben) | WCS-Fehler | Eigenbewegungen, helle Sterne (robuste Streuung RA/Dec) |
|---|---|---|
| ohne Korrektur | 11,4 mas | 2,9 / 1,2 mas/yr |
| Korrektur mit alter Formel | 13,6 mas | 11 / 11 mas/yr |
| Korrektur mit korrigierter Formel | 8,0 mas | 23 / 21 mas/yr |
| zusätzlich `reproj_fgroup()` vor der Schlussberechnung | 8,0 mas | 2,9 / 1,2 mas/yr |

- **Formel** (Abschnitt 10): Mit der alten Formel verschlechterte die Korrektur die Lösung. Das ist ein plausibler Grund für das Abschalten.
- **Fehlende Reprojektion (behoben):** Nach dem dritten Lösungsschritt fehlte `reproj_fgroup()`. Die abschließende Eigenbewegungsberechnung lief dann auf korrigierten Positionen mit veralteter WCS, und die ausgegebenen Eigenbewegungen waren unbrauchbar. `makeit.c` reprojiziert jetzt vorher (nur wenn die Option aktiv ist).
- **Statistiken und Clipping (behoben):** Statistik und Clipping wurden nach dem dritten Lösungsschritt nicht neu berechnet, und dieser lief ohne Clipping. Siehe „Dritter Lösungsschritt“ unten.
- **Grundsätzliche Grenze (offen):** Der Löser hat keine Eigenbewegungen als freie Parameter. Der lineare Anteil des Eigenbewegungsfeldes aller Sterne (gewichtet wie im Löser) wird daher als zeitlich lineare Drift in die linearen WCS-Terme der Belichtungen übernommen. Gemessen sind etwa 0,2 mas/arcmin pro Jahr. Diese Drift erzeugt einen feldweiten Trend in den gemessenen Eigenbewegungen von etwa 3 mas/yr (nach Abzug eines linearen Feldtrends bleiben 0,2 mas/yr). Die Korrektur nutzt die im driftenden System gemessenen Eigenbewegungen und kann die Drift deshalb nicht entfernen; sie verbessert nur den nichtlinearen Anteil (3,5 → 2,0 mas). Auch ein Referenzkatalog auf der mittleren Epoche oder `ASTREF_WEIGHT 100` beseitigen die Drift nicht. Abhilfe brächte nur eine Propagation der Referenzsterne mit ihren Katalog-Eigenbewegungen auf die Epoche jeder einzelnen Belichtung.
- **`ASTREFEPOCH_TYPE`** wirkt nur für VizieR-Kataloge, nicht für Referenzkataloge aus einer Datei (`ASTREF_CATALOG FILE`).

Die Drift lässt sich über die Eigenbewegungen des Referenzkatalogs verankern (`ASTREFPROP_CORRECT`, nächster Unterabschnitt).

### Neue Option `ASTREFPROP_CORRECT` (Standard `N`)

Ist `ASTREFPROP_CORRECT Y` gesetzt, rechnet `reproj_fgroup()` alle Detektionen eines Sterns, der im Referenzkatalog eine Eigenbewegung hat, mit dieser Katalog-Eigenbewegung auf die Epoche des Referenzsterns um. Das geschieht vor jedem Lösungsschritt und vor Statistik und Clipping.

- Die Eigenbewegung wird wie beim Epochenwechsel in `astrefcat.c` mit `|μ|²/(|μ|²+|σ_μ|²)` gedämpft, unabhängig von `ASTREFREGUL_TYPE`.
- Geändert werden nur die projizierten Positionen (`projpos`), nicht die Pixel- und Himmelspositionen.
- Vor der Messung der Eigenbewegungen (`COMPUTE_PROPERMOTIONS`) wird ohne Korrektur neu projiziert.
- Anders als `CORRECT_PROPERMOTIONS` ist das nicht zirkulär, weil die Eigenbewegungen von außen kommen.
- Ohne Eigenbewegungen im Referenzkatalog hat die Option keine Wirkung.

Ergebnisse mit den Testdaten oben (`INCLUDE_ASTREFCATALOG Y`):

| Referenzkatalog | `ASTREFPROP_CORRECT` | WCS-Fehler | Eigenbewegung Referenzsterne RA/Dec (robuste Streuung) | externe Residuen / χ² |
|---|---|---|---|---|
| Epoche 2016 | N | 11,4 mas | 2,6 / 1,0 mas/yr | 31 mas / 3,2 |
| Epoche 2016 | Y | 7,6 mas | 0,9 / 1,1 mas/yr | 15 mas / 0,59 |
| mittlere Epoche 2018 | N | 7,9 mas | 2,5 / 1,1 mas/yr | 16 mas / 0,94 |
| mittlere Epoche 2018 | Y | **5,0 mas** | **0,63 / 0,66 mas/yr** | 14 mas / 0,52 |

Die zeitliche Drift der Rotation verschwindet mit dem Referenzkatalog auf der mittleren Epoche praktisch vollständig. Am besten wirkt die Option daher zusammen mit `ASTREFEPOCH_TYPE FIELDS_AVERAGE` (nur VizieR-Kataloge). Bei Katalogen aus einer Datei sollten die Positionen auf eine Epoche nahe der Beobachtungen gebracht werden.

Verbleibende Grenze: Sterne ohne Referenz-Eigenbewegung tragen weiter zur Drift bei. In diesen pessimistischen Testdaten, in denen auch schwache Sterne zu 20 % schnell sind, sind das etwa 0,2 mas/yr/arcmin. Diese Sterne zusätzlich mit ihren gemessenen Eigenbewegungen zu korrigieren (`CORRECT_PROPERMOTIONS`) schien zunächst das Ergebnis zu verschlechtern. Die Ursache war das fehlende Clipping im dritten Lösungsschritt. Nach dessen Behebung ist die Kombination die beste Variante (nächster Unterabschnitt).

`tests/test_propmotion01.py` prüft die Option in einem dritten Lauf: robuste Streuung der Eigenbewegungen der Referenzsterne unter 2 mas/yr; gemessen 1,15/1,12, ohne die Korrektur 2,52 in RA.

### Dritter Lösungsschritt (`CORRECT_PROPERMOTIONS`)

Mit `CORRECT_PROPERMOTIONS Y` folgt auf die beiden üblichen Lösungsschritte ein dritter, auf eigenbewegungskorrigierten Positionen. Dabei gab es zwei Probleme:

- **Kein Clipping.** Das Clipping entfernt Ausreißer nur aus den Ketten verknüpfter Detektionen; es markiert sie nicht dauerhaft. Die neue Kreuzidentifikation vor dem dritten Schritt hat alle zuvor entfernten Ausreißer wieder eingefügt.
- **Veraltete Statistiken.** Danach wurden weder Statistik noch Clipping neu berechnet. Konsolenausgabe und XML-Statistiken beschrieben die Lösung vor der Korrektur. Im Test waren sie in allen Varianten identisch, obwohl die WCS-Genauigkeit zwischen 3,5 und 7,2 mas lag.

Jetzt wird vor dem dritten Schritt erneut geclippt. Danach folgen wie nach dem zweiten Schritt Kreuzidentifikation, Statistik, Clipping und die Ausgabe der Statistiktabellen („(proper motion corrected)“). Die Ausgabe ist dafür in die Funktion `astrstats_report()` in `makeit.c` ausgelagert. `CORRECT_PROPERMOTIONS` ist wieder als Schlüsselwort verfügbar (Standard `N`, nur in `scamp -dd`). Es sollte zusammen mit `ASTREFPROP_CORRECT Y` verwendet werden; ohne dieses ist die Korrektur zirkulär und bringt wenig.

Ergebnisse (Testdaten oben, Referenzkatalog auf der mittleren Epoche, `INCLUDE_ASTREFCATALOG Y`):

| `CORRECT_PROPERMOTIONS` | `ASTREFPROP_CORRECT` | WCS-Fehler | Eigenbewegung Referenzsterne RA/Dec |
|---|---|---|---|
| N | N | 7,9 mas | 2,52 / 1,05 mas/yr |
| Y (ohne Clipping, alt) | N | 6,9 mas | 2,47 / 1,04 mas/yr |
| N | Y | 5,0 mas | 0,63 / 0,66 mas/yr |
| Y (ohne Clipping, alt) | Y | 7,2 mas | 1,06 / 0,73 mas/yr |
| **Y (mit Clipping)** | **Y** | **3,5 mas** | **0,47 / 0,38 mas/yr** |

Mit dem Referenzkatalog auf Epoche 2016 sinkt der WCS-Fehler mit beiden Optionen von 7,6 (nur `ASTREFPROP_CORRECT`) auf 4,9 mas. Auch der feldweite Trend der schwachen Sterne ohne Referenz verschwindet weitgehend.

`tests/test_propmotion01.py` prüft beide Optionen über die robuste Streuung der Eigenbewegungen der Referenzsterne (quadratisches Mittel beider Achsen):

| Lauf | Wert | Grenze |
|---|---|---|
| ohne Korrektur | 1,87 mas/yr | – |
| `ASTREFPROP_CORRECT Y` | 1,13 mas/yr | < 1,5 |
| beide Optionen | 0,70 mas/yr | < 0,9 |
| beide, ohne Clipping vor dem dritten Schritt (Gegenprobe) | 1,49 mas/yr | schlägt fehl |

Alle Ergebnisse stammen aus synthetischen Daten. Eine Prüfung mit echten Mehrepochen-Daten (z. B. Gaia über VizieR) steht aus.

## 12. Prüfung der Astrometrie (Branch `astrom-tests`)

### Phase 0: Regressionsvergleich mit Upstream

Stand: 17.11.2026. Frage: Verändern unsere Änderungen (Abschnitte 1–11) die astrometrische Standardlösung?

**Vorgehen:**
- Verglichen wurde Upstream `72b7e76` (Basis aller Änderungen) mit `master` (`368b6f5`).
- Upstream ließ sich mit gcc + MKL nicht konfigurieren (Abschnitt 1). Deshalb wurden im Upstream-Worktree nur `configure.ac`, `m4/` und `Makefile.am` von `master` übernommen; `src/` ist unverändert Upstream. Beide Binaries nutzen so dieselben Bibliotheken (gcc 11, MKL).
- Alle Läufe mit `NTHREADS 1` und `MKL_NUM_THREADS=1`, damit sie deterministisch sind.
- Das neue Skript `tests/compare_heads.py` wertet zwei `.head`-Lösungen auf einem 21×41-Pixelgitter jedes Chips aus und meldet die größte Positionsdifferenz. Gegenprobe: Eine Verschiebung von CRVAL1 um 1e-4° wird mit 284 mas erkannt (erwartet 360 mas · cos δ = 284 mas).

| Szenario | Daten | Optionen | `.head` | Kataloge/XML |
|---|---|---|---|---|
| M1 | Megacam, 8 Belichtungen × 36 Chips, Gaia DR1 | `test_integration01.conf` (`SAME_CRVAL`, `INSTRUMENT`, Grad 4) | identisch | XML identisch¹ |
| M2 | wie M1 | `MOSAIC_TYPE LOOSE`, `STABILITY_TYPE EXPOSURE` | identisch | XML identisch¹ |
| M3 | wie M1 | `MOSAIC_TYPE FIX_FOCALPLANE` | identisch | XML identisch¹ |
| M4 | wie M1 | ein Instrument, Grad 3, Merged- und Full-Katalog | identisch | Kataloge byte-identisch |
| S1 | `gen_synth.py` (Einzelchip) | wie `test_synthetic01.py` | identisch | XML identisch¹ |
| PY | `gen_synth_pm.py` | `COMPUTE_PROPERMOTIONS Y`, `INCLUDE_ASTREFCATALOG Y` | identisch | Merged-Katalog identisch |
| PN | `gen_synth_pm.py` | `COMPUTE_PROPERMOTIONS Y`, `INCLUDE_ASTREFCATALOG N` | identisch | Eigenbewegungen verschieden² |

¹ Abgesehen von Pfaden, Laufzeit und `Flags_Mask` (Upstream: falsch 16711920, jetzt 240, Abschnitt 9).
² Erwartet, das ist der Fix in `proper.c:504` (Abschnitt 11). Anteil der Quellen ohne Eigenbewegung: Upstream 88,7 %, jetzt 5,6 % (Quellen mit zu wenigen Detektionen).

**Ergebnis:** Ohne die neuen Optionen sind die astrometrischen Lösungen byte-identisch mit Upstream, auch für die Multichip-Kamera in drei Mosaikmodi. Die einzigen Unterschiede sind die beabsichtigten Korrekturen.

Nicht abgedeckt: Läufe mit mehreren Threads (dort ist mit Rundungsrauschen zu rechnen, Abschnitt 10) und die VizieR-Kataloge.

Zum Vergleich mit der Wahrheit (S1, Einzelchip): Positions-RMS je Belichtung 2,9–4,1 mas, Maximum 10 mas. Das liegt knapp an der Testgrenze von 10 mas (RMS) und zeigt, dass ein rauschfreier Test nötig ist, um Algorithmusfehler vom Rauschen zu trennen (Phase 1).
