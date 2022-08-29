# -*- coding: utf-8 -*-
#
# Syncopy's (deep) copy function
#

# Builtin/3rd party package imports
from copy import copy as py_copy
import shutil
import h5py
import numpy as np

# Syncopy imports
from syncopy.shared.parsers import data_parser
from syncopy.shared.errors import SPYInfo

__all__ = ["copy"]


# Return a deep copy of the current class instance
def copy(data):
    """
    Create a copy of the entire Syncopy object `data` on disk

    Parameters
    ----------
    data : Syncopy data object
        Object to be copied on disk

    Returns
    -------
    cpy : Syncopy data object
        Reference to the copied data object
        on disk

    Notes
    -----
    For copying only a subset of the `data` use :func:`syncopy.selectdata` directly
    with the default `inplace=False` parameter.

    Syncopy objects may also be copied using the class method ``.copy`` that
    acts as a wrapper for :func:`syncopy.copy`

    See also
    --------
    :func:`syncopy.save` : save to specific file path
    :func:`syncopy.selectdata` : creates copy of a selection with `inplace=False`
    """

    # Make sure `data` is a valid Syncopy data object
    data_parser(data, varname="data", writable=None, empty=False)

    dsize = np.prod(data.data.shape) * data.data.dtype.itemsize / 1024**2
    msg = (f"Copying {dsize:.2f} MB of data "
           f"to create new {data.__class__.__name__} object on disk")
    SPYInfo(msg)

    # shallow copy, captures also non-default/temporary attributes
    cpy = py_copy(data)
    data.clear()
    filename = data._gen_filename()

    # copy data on disk
    shutil.copyfile(data.filename, filename)
    print(f"copy: the SOURCE h5py file has entries: {h5py.File(data.filename, mode='r').keys()}")
    print(f"copy: the copied H5py file has entries: {h5py.File(filename, mode='r').keys()}")

    # reattach properties
    for propertyName in data._hdfFileDatasetProperties:
        prop = getattr(data, "_" + propertyName)
        if isinstance(prop, h5py.Dataset):
            sourceName = prop.name
            print(f"copy: reattaching '{propertyName}': >>> hdf5 with sourceName '{sourceName}'")
            print(f"copy: reattaching '{propertyName}': >>>  the copied H5py file has entries: {h5py.File(filename, mode=cpy.mode).keys()}")
            setattr(cpy, "_" + propertyName,
                    h5py.File(filename, mode=cpy.mode)[sourceName])
        else:   # What could this be?
            print(f"copy: reattaching '{propertyName}': >>> NOT hdf5 with sourceName '{sourceName}'")
            setattr(cpy, "_" + propertyName, prop)

    cpy.filename = filename
    return cpy
