/*
*				mosaic.c
*
* Process mosaics.
*
*%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
*
*	This file part of:	SCAMP
*
*	Copyright:		(C) 2002-2020 IAP/CNRS/SorbonneU
*
*	License:		GNU General Public License
*
*	SCAMP is free software: you can redistribute it and/or modify
*	it under the terms of the GNU General Public License as published by
*	the Free Software Foundation, either version 3 of the License, or
* 	(at your option) any later version.
*	SCAMP is distributed in the hope that it will be useful,
*	but WITHOUT ANY WARRANTY; without even the implied warranty of
*	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
*	GNU General Public License for more details.
*	You should have received a copy of the GNU General Public License
*	along with SCAMP. If not, see <http://www.gnu.org/licenses/>.
*
*	Last modified:		12/08/2020
*
*%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%*/

#ifdef HAVE_CONFIG_H
#include        "config.h"
#endif

#ifdef USE_THREADS
#include <pthread.h>
#endif
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
 
#include "define.h"
#include "globals.h"
#include "field.h"
#include "fits/fitscat.h"
#include "fitswcs.h"
#include "match.h"
#include "mosaic.h"
#include "misc.h"
#include "prefs.h"
#include "astrefcat.h"
#include "samples.h"

#ifdef USE_THREADS
#include "threads.h"
#endif

#ifdef HAVE_ATLAS
#include ATLAS_LAPACK_H
#endif

#ifdef HAVE_LAPACKE
#include LAPACKE_H
#endif

/*------------------- global variables for multithreading -------------------*/
#ifdef USE_THREADS
 pthread_t		*mosaic_thread;
 pthread_mutex_t	mosaic_adjmutex;
 fieldstruct		**pthread_mosaic_fields;
 int			*pthread_mosaic_sviewflag,
			pthread_mosaic_endflag, pthread_mosaic_nset,
			pthread_mosaic_nfield,
			pthread_mosaic_lindex, pthread_mosaic_sindex,
			pthread_mosaic_sviewindex;
#endif

/****** adjust_mosaic ********************************************************
PROTO	void adjust_mosaic(fieldstruct **fields, int nfield)
PURPOSE	Adjust the relative positioning of mosaic elements (FITS extensions).
INPUT	ptr to the array of field pointers,
	number of fields.
OUTPUT	-.
NOTES	Uses the global preferences. All input fields must have a
	locate_field() up to date.
AUTHOR	E. Bertin (IAP)
VERSION	27/09/2004
 ***/
void	adjust_mosaic(fieldstruct **fields, int nfield)
  {
   fieldstruct	**matchfields,
		*field;
   setstruct	**sets;
   char		str[88];
   double	*wcsmean;
   int		d,f,l,s, nmatchfield, naxis, nlabel, flag;

  NFPRINTF(OUTPUT, "Making mosaic adjustments...");

  naxis = 0;		/* Avoid gcc -Wall warnings */
/* First step: convert CRVAL shifts to CRPIX variations */
  flag = 1;
  for (f=0; f<nfield; f++)
    {
    field = fields[f];
    if (prefs.mosaic_type[field->astromlabel] == MOSAIC_UNCHANGED)
      continue;
/*-- Use the average field center as a the new projection center */
    sprintf(str, "Computing set shifts for field %d/%d", f+1, nfield);
    NFPRINTF(OUTPUT, str);
    wcsmean = field->meanwcspos;
    naxis = field->naxis;
    sets = field->set;
    if (prefs.mosaic_type[field->astromlabel] == MOSAIC_SAMECRVAL)
      for (s=0; s<field->nset; s++)
        {
        for (d=0; d<naxis; d++)
          sets[s]->wcs->crval[d] = wcsmean[d];
        init_wcs(sets[s]->wcs);
        range_wcs(sets[s]->wcs);
        invert_wcs(sets[s]->wcs);
        }
    else
      for (s=0; s<field->nset; s++)
        crval_to_crpix(sets[s]->wcs, wcsmean);

    if (prefs.mosaic_type[field->astromlabel] == MOSAIC_FIXFOCALPLANE)
      flag = 0;

    }

/* Leave if every field has to be left unchanged */
  if (flag)
    return;

/* Do the job separately for each instrument */
  if ((nlabel=prefs.nastrinstrustr)>1)
    {
    QMALLOC(matchfields, fieldstruct *, nfield);
    nmatchfield = 0;
    } 
  else
    {
    nlabel = 1;
    matchfields = fields;
    nmatchfield = nfield;
    }

  for (l=0; l<nlabel; l++)
    {
    if (prefs.mosaic_type[l] != MOSAIC_FIXFOCALPLANE)
      continue;
    if (nlabel>1)
      {
      nmatchfield = 0;
      for (f=0; f<nfield; f++)
        if (fields[f]->astromlabel == l)
          matchfields[nmatchfield++] = fields[f];
      }

/*-- Compute median reduced coords between the optic center and ext. corners */
#ifdef USE_THREADS
    pthread_adjust_sets(matchfields, nmatchfield, l);
#else
    for (s=0; s<matchfields[0]->nset; s++)
      {
      sprintf(str, "Instrument A%-2d: Adjusting set %d/%d",
	l+1, s+1, matchfields[0]->nset);
      NFPRINTF(OUTPUT, str);
      adjust_set(matchfields, nmatchfield, s);
      }
#endif
    }

  if (nlabel>1)
    free(matchfields);

  return;
  }


/****** adjust_set ***********************************************************
PROTO	void adjust_set(fieldstruct **fields, int nfield, int s)
PURPOSE	Adjust the relative positioning of one mosaic element (FITS extension).
INPUT	ptr to the array of field pointers,
	number of fields,
	extension number.
OUTPUT	-.
NOTES	Uses the global preferences. All input fields must have a
	locate_field() up to date.
AUTHOR	E. Bertin (IAP)
VERSION	13/12/2011
 ***/
void	adjust_set(fieldstruct **fields, int nfield, int s)
  {
#if defined(HAVE_LAPACKE)
   lapack_int	ipiv[NAXIS];
#else
   int		ipiv[NAXIS];
#endif
   double	x[(NAXIS+1)*NAXIS], cd[NAXIS*NAXIS],
		rawpos[NAXIS], redpos[NAXIS],
		*medstack;
   int		*naxisn,
		d,e,f,i, naxis, noksets;


  naxisn = fields[0]->set[s]->wcs->naxisn;
  naxis = fields[0]->set[s]->wcs->naxis;
  QMALLOC(medstack, double, nfield*naxis);
  for (d=0; d<naxis; d++)
    rawpos[d] = 0.5;
  for (i=-1; i<naxis; i++)
    {
    if (i>=0)
      {
      rawpos[i] = naxisn[i]+0.5;	/* one corner*/
      if (i)
        rawpos[i-1] = 0.5;
      }
    noksets = 0;
    for (f=0; f<nfield; f++)
      {
      if (fields[f]->set[s]->nsample < prefs.fixfocalplane_nmin)
        continue;
      raw_to_red(fields[f]->set[s]->wcs, rawpos, redpos);
      for (d=0; d<naxis; d++)
        medstack[d*nfield+noksets] = redpos[d];
      noksets++;
      }
    if (noksets)
      for (d=0; d<naxis; d++)
/*------ Median of the corner coordinates */
        x[(i+1)*naxis+d] = fast_median(medstack+d*nfield, noksets);
    else
      {
/*---- No valid CCD, take the first one as a reference */
      raw_to_red(fields[0]->set[s]->wcs, rawpos, redpos);
      for (d=0; d<naxis; d++)
        x[(i+1)*naxis+d] = redpos[d];
      }
    }
/*-- Derive the CD's */
  for (d=0; d<naxis; d++)
    for (e=0; e<naxis; e++)
      cd[d*naxis+e] = (x[(e+1)*naxis+d] - x[d])/naxisn[e];
  for (f=0; f<nfield; f++)
    memcpy(fields[f]->set[s]->wcs->cd, cd,naxis*naxis*sizeof(double));
/* Derive the CRPIXs */
#if defined(HAVE_LAPACKE)
  LAPACKE_dgesv(LAPACK_ROW_MAJOR, naxis, 1, cd, naxis, ipiv, x, 1);
#else
  clapack_dgesv(CblasRowMajor, naxis, 1, cd, naxis, ipiv, x, naxis);
#endif
  for (f=0; f<nfield; f++)
    for (d=0; d<naxis; d++)
      fields[f]->set[s]->wcs->crpix[d] = 0.5 - x[d];

/* Initialize other WCS structures */
  for (f=0; f<nfield; f++)
    {
    init_wcs(fields[f]->set[s]->wcs);
/*-- Find the range of coordinates */
    range_wcs(fields[f]->set[s]->wcs);
/*-- Invert projection corrections */
    invert_wcs(fields[f]->set[s]->wcs);
    }

  free(medstack);

  return;
  }


/****** shift_tpv ************************************************************
PROTO	int shift_tpv(wcsstruct *wcs, double *dred)
PURPOSE	Move the origin of the TPV distortion polynomials to the reduced
	coordinates dred: P(x) -> Q(x) = P(x+dred) - P(dred).
INPUT	ptr to the WCS structure,
	shift in reduced (intermediate) coordinates.
OUTPUT	RETURN_OK if the polynomials were shifted, RETURN_ERROR if they
	contain terms that cannot be shifted (radial terms).
NOTES	Exact for the polynomial terms (Taylor shift). The constant terms
	of Q are zero, so that the new reference pixel maps onto the new CRVAL.
AUTHOR	T. Erben, Claude
VERSION	17/11/2026
 ***/
static int	shift_tpv(wcsstruct *wcs, double *dred)
  {
   static const int pvindex[8][8] =	{
	{0,1,4,7,12,17,24,31},
	{2,5,8,13,18,25,32,0},
	{6,9,14,19,26,33,0,0},
	{10,15,20,27,34,0,0,0},
	{16,21,28,35,0,0,0,0},
	{22,29,36,0,0,0,0,0},
	{30,37,0,0,0,0,0,0},
	{38,0,0,0,0,0,0,0}};
   static const int radial[4] = {3, 11, 23, 39};
   double	pa[8][8], pb[8][8], binom[8][8], powx[8], powy[8],
		*projp, dx, dy;
   int		axis[2], d, i,j,k,l, p, idx;

  axis[0] = wcs->lng;
  axis[1] = wcs->lat;
  projp = wcs->projp;
  for (d=0; d<2; d++)
    {
    for (p=0; p<4; p++)
      if (projp[radial[p]+100*axis[d]] != 0.0)
        return RETURN_ERROR;
    for (p=40; p<100; p++)
      if (projp[p+100*axis[d]] != 0.0)
        return RETURN_ERROR;
    }

  for (i=0; i<8; i++)
    for (k=0; k<8; k++)
      binom[i][k] = (k==0 || k==i)? 1.0
			: (k<i? binom[i-1][k-1] + binom[i-1][k] : 0.0);
  dx = dred[axis[0]];
  dy = dred[axis[1]];
  powx[0] = powy[0] = 1.0;
  for (i=1; i<8; i++)
    {
    powx[i] = powx[i-1]*dx;
    powy[i] = powy[i-1]*dy;
    }

  for (d=0; d<2; d++)
    {
/*-- pa[i][j]: coefficient of x^i y^j (x = lng, y = lat reduced coords); */
/*-- the lat axis polynomial has the roles of x and y swapped in TPV */
    for (i=0; i<8; i++)
      for (j=0; j<8; j++)
        pa[i][j] = (i+j<8)?
		projp[(d? pvindex[i][j] : pvindex[j][i]) + 100*axis[d]] : 0.0;
    for (k=0; k<8; k++)
      for (l=0; k+l<8; l++)
        {
        pb[k][l] = 0.0;
        for (i=k; i<8; i++)
          for (j=l; i+j<8; j++)
            pb[k][l] += pa[i][j]*binom[i][k]*binom[j][l]*powx[i-k]*powy[j-l];
        }
    pb[0][0] = 0.0;
    for (k=0; k<8; k++)
      for (l=0; k+l<8; l++)
        {
        idx = d? pvindex[k][l] : pvindex[l][k];
        projp[idx+100*axis[d]] = pb[k][l];
        }
    }

  return RETURN_OK;
  }


/****** crval_to_crpix *******************************************************
PROTO	void crval_to_crpix(wcsstruct *wcs, double *wcspos)
PURPOSE	Keep a WCS projection approx. the same but with a new CRVAL.
INPUT	ptr to the WCS structure,
	new CRVAL vector.
OUTPUT	-.
NOTES	The updated WCS is an approximation of the exact one.
	The new CRPIX is the pixel of the new CRVAL in the old WCS; TPV
	distortion polynomials are shifted accordingly (shift_tpv()).
	Before, the polynomials were kept unchanged, so that their constant
	terms were applied twice (offsets of up to arcseconds for
	MOSAIC_TYPE LOOSE and FIX_FOCALPLANE with PV1_0/PV2_0 != 0).
AUTHOR	E. Bertin (IAP)
VERSION	17/11/2026
 ***/
void	crval_to_crpix(wcsstruct *wcs, double *wcspos)
  {
   double	rawpos[NAXIS], redpos[NAXIS], a[NAXIS*NAXIS],b[NAXIS*NAXIS],
		*c,*at,
		val, cas, sas, angle, dlng;
   int		i,j,k, lng,lat, naxis;

  lng = wcs->lng;
  lat = wcs->lat;
  naxis = wcs->naxis;

  wcs_to_raw(wcs, wcspos, rawpos);

/* Move the origin of the distortion polynomials to the new reference pixel */
  if (lng != lat && wcs->nprojp)
    {
    raw_to_red(wcs, rawpos, redpos);
    if (shift_tpv(wcs, redpos) != RETURN_OK)
      warning("radial or high-order PV terms: ",
	"mosaic adjustment may be inaccurate");
    }

  if (lng != lat)
    {
/*-- Compute the angle difference towards the north pole induced by the shift*/
    dlng = wcspos[lng] - wcs->crval[lng];
    angle = (fabs(dlng)>1e-10) ?
	(atan2(sin(wcspos[lat]*DEG)*cos(dlng*DEG)
			- cos(wcspos[lat]*DEG)*tan(wcs->crval[lat]*DEG),
		sin(dlng*DEG))
	+ atan2(sin(wcs->crval[lat]*DEG)*cos(dlng*DEG)
			- cos(wcs->crval[lat]*DEG)*tan(wcspos[lat]*DEG),
		sin(dlng*DEG)))/DEG
	: 0.0;
/*-- A = B*C */
    c = wcs->cd;
/*-- The B matrix is made of 2 numbers */
    cas = cos(angle*DEG);
    sas = sin(angle*DEG);
    for (i=0; i<naxis; i++)
      b[i+i*naxis] = 1.0;
    b[lng+lng*naxis] = cas;
    b[lat+lng*naxis] = -sas;
    b[lng+lat*naxis] = sas;
    b[lat+lat*naxis] = cas;
    at = a;
    for (j=0; j<naxis; j++)
      for (i=0; i<naxis; i++)
        {
        val = 0.0;
        for (k=0; k<naxis; k++)
          val += b[k+j*naxis]*c[i+k*naxis];
        *(at++) = val;
        }

    at = a;

    for (i=0; i<naxis*naxis; i++)
      *(c++) = *(at++);
    }

  for (i=0; i<naxis; i++)
    {
    wcs->crval[i] = wcspos[i];
    wcs->crpix[i] = rawpos[i];
    }

/* Initialize other WCS structures */
  init_wcs(wcs);
/* Find the range of coordinates */
  range_wcs(wcs);
/* Invert projection corrections */
  invert_wcs(wcs);
  if (lng == lat)
    return;

  return;
  }


#ifdef USE_THREADS

/****** pthread_adjust_set ***************************************************
PROTO   void *pthread_adjust_set(void *arg)
PURPOSE thread that takes care of adjusting mosaic elements.
INPUT   Pointer to the thread number.
OUTPUT  -.
NOTES   Relies on global variables.
AUTHOR  E. Bertin (IAP)
VERSION 12/08/2020
 ***/
void    *pthread_adjust_set(void *arg)
  {
   char	str[80];
   int	sindex;

  sindex = -1;
  threads_gate_sync(pthread_startgate);
  while (!pthread_mosaic_endflag)
    {
    QPTHREAD_MUTEX_LOCK(&mosaic_adjmutex);
    if (sindex>-1)
/*---- Indicate that the field info is now suitable for viewing */
      pthread_mosaic_sviewflag[sindex] = 1;
    while (pthread_mosaic_sviewindex < pthread_mosaic_nset
	&& pthread_mosaic_sviewflag[pthread_mosaic_sviewindex])
      {
      sprintf(str, "Instrument A%-2d: Adjusting set %d/%d",
	pthread_mosaic_lindex+1, ++pthread_mosaic_sviewindex, pthread_mosaic_nset);
      NFPRINTF(OUTPUT, str);
      }
    if (pthread_mosaic_sindex < pthread_mosaic_nset)
      {
      sindex = pthread_mosaic_sindex++;
      QPTHREAD_MUTEX_UNLOCK(&mosaic_adjmutex);
/*---- Adjust set */
      adjust_set(pthread_mosaic_fields, pthread_mosaic_nfield, sindex);
      }
    else
      {
      QPTHREAD_MUTEX_UNLOCK(&mosaic_adjmutex);
/*---- Wait for the input buffer to be updated */
      threads_gate_sync(pthread_stopgate);
/* ( Master thread process loads and saves new data here ) */
      threads_gate_sync(pthread_startgate);
      }
    }

  pthread_exit(NULL);

  return (void *)NULL;
  }


/****** pthread_adjust_sets ***************************************************
PROTO   void pthread_adjust_sets(fieldstruct **fields, int nfield, int l)
PURPOSE Adjust the relative positioning of mosaic elements in parallel using
	threads.
INPUT   Pointer to field structure pointers,
	number of set,
	number of fields,
	current astrometric instrument index (label).
OUTPUT  -.
NOTES   Relies on global variables.
AUTHOR  E. Bertin (IAP)
VERSION 12/08/2020
 ***/
void    pthread_adjust_sets(fieldstruct **fields, int nfield, int l)
  {
   static pthread_attr_t	pthread_attr;
   int				*proc,
				p;

/* Number of active threads */
  nproc = prefs.nthreads;
  pthread_mosaic_fields = fields;
  pthread_mosaic_nfield = nfield;
  pthread_mosaic_nset = fields[0]->nset;
  QCALLOC(pthread_mosaic_sviewflag, int, pthread_mosaic_nset);
/* Set up multi-threading stuff */
  QMALLOC(proc, int, nproc);
  QMALLOC(mosaic_thread, pthread_t, nproc);
  QPTHREAD_MUTEX_INIT(&mosaic_adjmutex, NULL);
  QPTHREAD_ATTR_INIT(&pthread_attr);
  QPTHREAD_ATTR_SETDETACHSTATE(&pthread_attr, PTHREAD_CREATE_JOINABLE);
  pthread_startgate = threads_gate_init(nproc+1, NULL);
  pthread_stopgate = threads_gate_init(nproc+1, NULL);
/* Start the reading threads */
  for (p=0; p<nproc; p++)
    {
    proc[p] = p;
    QPTHREAD_CREATE(&mosaic_thread[p], &pthread_attr, &pthread_adjust_set, &proc[p]);
    }
  QPTHREAD_MUTEX_LOCK(&mosaic_adjmutex);
  pthread_mosaic_sindex = pthread_mosaic_sviewindex = 0;
  pthread_mosaic_endflag = 0;
  pthread_mosaic_lindex = l;
  QPTHREAD_MUTEX_UNLOCK(&mosaic_adjmutex);
/* Release threads!! */
  threads_gate_sync(pthread_startgate);
/* ( Slave threads process the current buffer data here ) */
  threads_gate_sync(pthread_stopgate);
  pthread_mosaic_endflag = 1;
/* (Re-)activate existing threads... */
  threads_gate_sync(pthread_startgate);
/* ... and shutdown all threads */
  for (p=0; p<nproc; p++)
    QPTHREAD_JOIN(mosaic_thread[p], NULL);
/* Clean up multi-threading stuff */
  threads_gate_end(pthread_startgate);
  threads_gate_end(pthread_stopgate);
  QPTHREAD_MUTEX_DESTROY(&mosaic_adjmutex);
  QPTHREAD_ATTR_DESTROY(&pthread_attr);
  free(pthread_mosaic_sviewflag);
  free(proc);
  free(mosaic_thread);
  }

#endif

