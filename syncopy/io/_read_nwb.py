# -*- coding: utf-8 -*-
#
# Load data from NWB file
#

# Builtin/3rd party package imports
import os
import h5py
import subprocess
import numpy as np

# Local imports
from syncopy import __nwb__
from syncopy.datatype.continuous_data import AnalogData
from syncopy.datatype.discrete_data import EventData
from syncopy.shared.errors import SPYError, SPYValueError, SPYWarning
from syncopy.shared.parsers import io_parser, scalar_parser

# Conditional imports
if __nwb__:
    import pynwb

# Global consistent error message if NWB is missing
nwbErrMsg = "\nSyncopy <core> WARNING: Could not import 'pynwb'. \n" +\
          "{} requires a working pyNWB installation. \n" +\
          "Please consider installing 'pynwb', e.g., via conda: \n" +\
          "\tconda install -c conda-forge pynwb\n" +\
          "or using pip:\n" +\
          "\tpip install pynwb"

__all__ = ["read_nwb"]


def read_nwb(filename, memuse=3000):
    """
    Coming soon...

    memuse : scalar
        Approximate in-memory cache size (in MB) for writing data to disk
    """

    # Abort if NWB is not installed
    if not __nwb__:
        raise SPYError(nwbErrMsg.format("read_nwb"))

    # Check if file exists
    nwbPath, nwbBaseName = io_parser(filename, varname="filename", isfile=True, exists=True)
    nwbFullName = os.path.join(nwbPath, nwbBaseName)

    # Ensure `memuse` makes sense`
    try:
        scalar_parser(memuse, varname="memuse", lims=[0, np.inf])
    except Exception as exc:
        raise exc

    # First, perform some basal validation w/NWB
    try:
        subprocess.run(["python", "-m", "pynwb.validate", nwbFullName], check=True)
    except subprocess.CalledProcessError as exc:
        err = "NWB file validation failed. Original error message: {}"
        raise SPYError(err.format(str(exc)))

    # Load NWB meta data from disk
    nwbio = pynwb.NWBHDF5IO(nwbFullName, "r", load_namespaces=True)
    nwbfile = nwbio.read()

    # Allocate lists for storing temporary NWB info: IMPORTANT use lists to preserve
    # order of data chunks/channels
    nSamples = 0
    nChannels = 0
    chanNames = []
    tStarts = []
    sRates = []
    dTypes = []
    angSeries = []
    ttlVals = []
    ttlChans = []
    ttlDtypes = []

    # If the file contains `epochs`, use it to infer trial information
    hasTrials = "epochs" in nwbfile.fields.keys()

    # Access all (supported) `acquisition` fields in the file
    for acqName, acqValue in nwbfile.acquisition.items():

        # Actual extracellular analog time-series data
        if isinstance(acqValue, pynwb.ecephys.ElectricalSeries):

            channels = acqValue.electrodes[:].location
            if channels.unique().size == 1:
                SPYWarning("No channel names found for {}".format(acqName))
            else:
                chanNames += channels.to_list()

            dTypes.append(acqValue.data.dtype)
            if acqValue.channel_conversion is not None:
                dTypes.append(acqValue.channel_conversion.dtype)

            tStarts.append(acqValue.starting_time)
            sRates.append(acqValue.rate)
            nChannels += acqValue.data.shape[1]
            nSamples = max(nSamples, acqValue.data.shape[0])
            angSeries.append(acqValue)

        # TTL event pulse data
        elif "abc.TTLs" in str(acqValue.__class__):

            if acqValue.name == "TTL_PulseValues":
                ttlVals.append(acqValue)
            elif acqValue.name == "TTL_ChannelStates":
                ttlChans.append(acqValue)
            else:
                lgl = "TTL data exported via `esi-oephys2nwb`"
                act = "unformatted TTL data '{}'"
                raise SPYValueError(lgl, varname=acqName, actual=act.format(acqValue.description))

            ttlDtypes.append(acqValue.data.dtype)
            ttlDtypes.append(acqValue.timestamps.dtype)

        # Unsupported
        else:
            lgl = "supported NWB data class"
            raise SPYValueError(lgl, varname=acqName, actual=str(acqValue.__class__))

    # If the NWB data is split up in "trials" (i.e., epochs), ensure things don't
    # get too wild (uniform sampling rates and timing offsets)
    if hasTrials:
        if all(tStarts) is None or all(sRates) is None:
            lgl = "acquisition timings defined by `starting_time` and `rate`"
            act = "`starting_time` or `rate` not set"
            raise SPYValueError(lgl, varname="starting_time/rate", actual=act)
        if np.unique(tStarts).size > 1 or np.unique(sRates).size > 1:
            lgl = "acquisitions with unique `starting_time` and `rate`"
            act = "`starting_time` or `rate` different across acquisitions"
            raise SPYValueError(lgl, varname="starting_time/rate", actual=act)
        epochs = nwbfile.epochs[:]
        trl = np.zeros((epochs.shape[0], 3), dtype=np.intp)
        trl[:, :2] = (epochs - tStarts[0]) * sRates[0]
    else:
        trl = np.array([[0, nSamples, 0]])

    # If TTL data was found, ensure we have exactly one set of values and associated
    # channel markers
    if max(len(ttlVals), len(ttlChans)) > min(len(ttlVals), len(ttlChans)):
        lgl = "TTL pulse values and channel markers"
        act = "pulses: {}, channels: {}".format(str(ttlVals), str(ttlChans))
        raise SPYValueError(lgl, varname=ttlVals[0].name, actual=act)
    if len(ttlVals) > 1:
        lgl = "one set of TTL pulses"
        act = "{} TTL data sets".format(len(ttlVals))
        raise SPYValueError(lgl, varname=ttlVals[0].name, actual=act)

    # Use provided TTL data to initialize `EventData` object
    if len(ttlVals) > 0:
        evtData = EventData(dimord=EventData._defaultDimord)
        h5evt = h5py.File(evtData.filename, mode="w")
        evtDset = h5evt.create_dataset("data", dtype=np.result_type(*ttlDtypes),
                                       shape=(ttlVals[0].data.size, 3))
        evtDset[:, 0] = ((ttlChans[0].timestamps[()] - tStarts[0]) / ttlChans[0].timestamps__resolution).astype(np.intp)
        evtDset[:, 1] = ttlVals[0].data[()]
        evtDset[:, 2] = ttlChans[0].data[()]
        evtData.data = evtDset
        evtData.samplerate = 1 / ttlChans[0].timestamps__resolution
        if hasTrials:
            evtData.trialdefinition = trl

    # Allocate `AnalogData` object and use generated HDF5 file-name to manually
    # allocate a target dataset for reading the NWB data
    angData = AnalogData(dimord=AnalogData._defaultDimord)
    angShape = [None, None]
    angShape[angData._defaultDimord.index("time")] = nSamples
    angShape[angData._defaultDimord.index("channel")] = nChannels
    h5ang = h5py.File(angData.filename, mode="w")
    angDset = h5ang.create_dataset("data", dtype=np.result_type(*dTypes), shape=angShape)

    # Compute actually available memory (divide by 2 since we're working with an add'l tmp array)
    memuse *= 1024**2 / 2
    chanCounter = 0

    # Process analog time series data and save stuff block by block (if necessary)
    # FIXME: >>>>>>>>>>>>>>>> Use tqdm here
    for acqValue in angSeries:

        # Given memory cap, compute how many data blocks can be grabbed per swipe
        nSamp = int(memuse / (np.prod(angDset.shape[1:]) * angDset.dtype.itemsize))
        rem = int(angDset.shape[0] % nSamp)
        nBlocks = [nSamp] * int(angDset.shape[0] // nSamp) + [rem] * int(rem > 0)

        # If channel-specific gains are set, load them now
        if acqValue.channel_conversion is not None:
            gains = acqValue.channel_conversion[()]

        # Write data block-wise to `angDset` (use `del` to wipe blocks from memory)
        # Use 'unsafe' casting to allow `tmp` array conversion int -> float
        endChan = chanCounter + acqValue.data.shape[1]
        for m, M in enumerate(nBlocks):
            tmp = acqValue.data[m * nSamp: m * nSamp + M, :]
            if acqValue.channel_conversion is not None:
                np.multiply(tmp, gains, out=tmp, casting="unsafe")
            angDset[m * nSamp: m * nSamp + M, chanCounter : endChan] = tmp
            del tmp

        # Update channel counter for next `acqValue``
        chanCounter += acqValue.data.shape[1]

    # Finalize angData
    angData.data = angDset
    angData.channel = chanNames
    angData.samplerate = sRates[0]
    angData.trialdefinition = trl

    # # Write log-entry
    # msg = "Read files v. {ver:s} ".format(ver=jsonDict["_version"])
    # msg += "{hdf:s}\n\t" + (len(msg) + len(thisMethod) + 2) * " " + "{json:s}"
    # out.log = msg.format(hdf=hdfFile, json=jsonFile)


    import ipdb; ipdb.set_trace()

