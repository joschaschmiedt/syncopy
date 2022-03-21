# -*- coding: utf-8 -*-
#
# Helper routines to normalize Fourier spectra
#

import numpy as np


def _norm_spec(ftr, nSamples, fs, mode='amplitude'):

    """
    Normalizes the complex Fourier transform to
    power spectral density of amplitude squaredunits.
    """

    # frequency bins
    if mode == 'density':
        delta_f = fs / nSamples
    elif mode == 'amplitude':
        delta_f = 1

    ftr *= np.sqrt(2) / (nSamples * np.sqrt(delta_f))

    return ftr


def _norm_taper(taper, windows, nSamples):

    """
    Helper function to normalize tapers such
    that the resulting spectra are normalized
    to power density units.
    """

    if taper == 'dpss':
        windows *= np.sqrt(nSamples)
    # weird 3 point normalization,
    # checks out exactly for 'hann' though
    elif taper != 'boxcar':
        windows *= np.sqrt(4 / 3) * np.sqrt(nSamples / windows.sum())

    return windows
