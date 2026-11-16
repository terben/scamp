dnl
dnl				acx_openblas.m4
dnl
dnl Figure out if the OpenBLAS library and header files are installed.
dnl
dnl %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
dnl
dnl	This file part of:	AstrOmatic software
dnl
dnl	Copyright:		(C) 2016 IAP/CNRS/UPMC
dnl
dnl	License:		GNU General Public License
dnl
dnl	AstrOmatic software is free software: you can redistribute it and/or
dnl	modify it under the terms of the GNU General Public License as
dnl	published by the Free Software Foundation, either version 3 of the
dnl	License, or (at your option) any later version.
dnl	AstrOmatic software is distributed in the hope that it will be useful,
dnl	but WITHOUT ANY WARRANTY; without even the implied warranty of
dnl	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
dnl	GNU General Public License for more details.
dnl	You should have received a copy of the GNU General Public License
dnl	along with AstrOmatic software.
dnl	If not, see <http://www.gnu.org/licenses/>.
dnl
dnl	Last modified:		12/10/2016
dnl
dnl %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
dnl
dnl @synopsis ACX_OPENBLAS([OPENBLAS_LIBSDIR, OPENBLAS_INCDIR, OPENBLAS_PFLAG,
dnl                  ILP64_FLAG, [ACTION-IF-FOUND[, ACTION-IF-NOT-FOUND]]])
dnl
dnl You may wish to use these variables in your default LIBS:
dnl
dnl        LIBS="$OPENBLAS_LIBS $LIBS"
dnl
dnl ACTION-IF-FOUND is a list of shell commands to run if OPENBLAS
dnl is found (HAVE_OPENBLAS is defined first), and ACTION-IF-NOT-FOUND
dnl is a list of commands to run it if it is not found.

AC_DEFUN([ACX_OPENBLAS], [
AC_REQUIRE([AC_CANONICAL_HOST])

dnl --------------------
dnl Search include files
dnl --------------------

OPENBLAS_ERROR=""
if test x$4 = xyes; then
  acx_openblas_suffix="64"
  OPENBLAS_CFLAGS="-DOPENBLAS_USE64BITINT -DLAPACK_ILP64"
else
  acx_openblas_suffix=""
  OPENBLAS_CFLAGS=""
fi

dnl Candidate header directories ("default" = compiler's default search path)
if test x$2 = x; then
dnl Upstream layout, then the directory advertised by pkg-config (e.g.
dnl .../openblas-pthread/ on Debian/Ubuntu), then the default path
  acx_openblas_pcdir=""
  if pkg-config --exists openblas$acx_openblas_suffix 2>/dev/null; then
    acx_openblas_pcdir=`pkg-config --variable=includedir \
	openblas$acx_openblas_suffix | sed 's|/*$|/|'`
  fi
  acx_openblas_dirs="openblas/ $acx_openblas_pcdir default"
  acx_openblas_where=""
else
  acx_openblas_dirs="$2/ $2/include/"
  acx_openblas_where=" in $2"
fi

dnl OpenBLAS's own cblas.h, recognized by its openblas_set_num_threads()
dnl declaration (other BLAS headers may be installed as plain cblas.h)
AC_MSG_CHECKING([for OpenBLAS's cblas.h])
acx_openblas_blash=""
for acx_openblas_d in $acx_openblas_dirs; do
  test "x$acx_openblas_d" = xdefault && acx_openblas_d=""
  AC_COMPILE_IFELSE([AC_LANG_PROGRAM([[#include <${acx_openblas_d}cblas.h>]],
	[[void (*f)(int) = openblas_set_num_threads; (void)f;]])],
	[acx_openblas_blash="${acx_openblas_d}cblas.h"; break])
done
if test "x$acx_openblas_blash" != x; then
  acx_openblas_ownblash="yes"
  AC_MSG_RESULT([$acx_openblas_blash])
else
  acx_openblas_ownblash="no"
  AC_MSG_RESULT([no])
dnl Fall back to any cblas.h
  AC_MSG_CHECKING([for cblas.h])
  for acx_openblas_d in $acx_openblas_dirs; do
    test "x$acx_openblas_d" = xdefault && acx_openblas_d=""
    AC_COMPILE_IFELSE([AC_LANG_PROGRAM([[#include <${acx_openblas_d}cblas.h>]])],
	[acx_openblas_blash="${acx_openblas_d}cblas.h"; break])
  done
  AC_MSG_RESULT([${acx_openblas_blash:-no}])
fi

AC_MSG_CHECKING([for lapacke.h])
acx_openblas_lapackeh=""
for acx_openblas_d in $acx_openblas_dirs; do
  test "x$acx_openblas_d" = xdefault && acx_openblas_d=""
  AC_COMPILE_IFELSE([AC_LANG_PROGRAM([[#include <${acx_openblas_d}lapacke.h>]])],
	[acx_openblas_lapackeh="${acx_openblas_d}lapacke.h"; break])
done
AC_MSG_RESULT([${acx_openblas_lapackeh:-no}])

if test "x$acx_openblas_blash" = x || test "x$acx_openblas_lapackeh" = x; then
  OPENBLAS_ERROR="OpenBLAS header files not found$acx_openblas_where!"
fi

if test "x$OPENBLAS_ERROR" = "x"; then
  AC_DEFINE_UNQUOTED(BLAS_H, "$acx_openblas_blash", [BLAS header filename.])
  AC_DEFINE_UNQUOTED(LAPACKE_H, "$acx_openblas_lapackeh", [LAPACKe header filename.])

dnl ----------------------------
dnl Search OpenBLAS library file
dnl ----------------------------

  OLIBS="$LIBS"
  LIBS=""
  if test x$1 = x; then
    acx_openblas_libopt=""
  else
    acx_openblas_libopt="-L$1"
  fi
dnl "openblasp" is the parallel version on e.g. Fedora
  AC_SEARCH_LIBS(
    [LAPACKE_dpotrf],
    ["openblasp"$acx_openblas_suffix "openblas"$acx_openblas_suffix],,
    [OPENBLAS_ERROR="OpenBLAS"$acx_openblas_suffix" library file not found!"],
    $acx_openblas_libopt
  )
dnl Some distributions (e.g., Debian/Ubuntu) ship LAPACKe in a separate
dnl library instead of bundling it with OpenBLAS
  if test "x$OPENBLAS_ERROR" != "x"; then
    unset ac_cv_search_LAPACKE_dpotrf
    AC_SEARCH_LIBS(
      [LAPACKE_dpotrf], ["lapacke"$acx_openblas_suffix],
      [
        OPENBLAS_ERROR=""
        ac_cv_search_LAPACKE_dpotrf="$ac_cv_search_LAPACKE_dpotrf -lopenblas$acx_openblas_suffix"
      ],,
      [$acx_openblas_libopt -lopenblas$acx_openblas_suffix]
    )
  fi
dnl Thread control: whatever the library name, the number of threads can be
dnl set if openblas_set_num_threads() is both declared and available
  if test "x$OPENBLAS_ERROR" = "x" && test x$3 = xyes; then
    if test "x$acx_openblas_ownblash" = xyes; then
      LIBS="$acx_openblas_libopt $ac_cv_search_LAPACKE_dpotrf"
      AC_MSG_CHECKING([for openblas_set_num_threads])
      AC_LINK_IFELSE([AC_LANG_PROGRAM([[#include <$acx_openblas_blash>]],
	[[openblas_set_num_threads(1);]])],
        [AC_MSG_RESULT([yes])
         AC_DEFINE(HAVE_OPENBLASP,1,
		[Define if the number of OpenBLAS threads can be set.])],
        [AC_MSG_RESULT([no])
         OPENBLAS_WARN="openblas_set_num_threads() not found: the number of OpenBLAS threads cannot be set!"])
    else
      OPENBLAS_WARN="OpenBLAS's cblas.h not found: the number of OpenBLAS threads cannot be set!"
    fi
  fi
  LIBS="$OLIBS"
fi

dnl -------------------------------------------------------------------------
dnl Finally execute ACTION-IF-FOUND/ACTION-IF-NOT-FOUND
dnl -------------------------------------------------------------------------

if test "x$OPENBLAS_ERROR" = "x"; then
  AC_DEFINE(HAVE_OPENBLAS,1, [Define if you have the OpenBLAS library and header files.])
  AC_DEFINE(HAVE_BLAS,1, [Define if you have the BLAS library and header files.])
  AC_DEFINE(HAVE_LAPACKE,1, [Define if you have the LAPACKe library and header files.])
  OPENBLAS_LIBS="$acx_openblas_libopt $ac_cv_search_LAPACKE_dpotrf"
  AC_SUBST(OPENBLAS_CFLAGS)
  AC_SUBST(OPENBLAS_LDFLAGS, "")
  AC_SUBST(OPENBLAS_LIBS)
  AC_SUBST(OPENBLAS_WARN)
  $5
else
  AC_SUBST(OPENBLAS_ERROR)
  $6
fi

])dnl ACX_OPENBLAS

