# core.py - SpykeWave basic datatype reference implementation
# 
# Created: January 7 2019
# Last modified by: Stefan Fuertinger [stefan.fuertinger@esi-frankfurt.de]
# Last modification time: <2019-02-08 17:52:32>

# Builtin/3rd party package imports
import numpy as np
import getpass
import socket
import time
import numbers
import inspect
from collections import OrderedDict, Iterator
from itertools import islice
    
# Local imports
from spykewave.utils import (spw_scalar_parser, spw_array_parser,
                             SPWTypeError, SPWValueError, spw_warning)
from spykewave import __version__
import spykewave as sw

__all__ = ["BaseData", "ChunkData", "Indexer"]

##########################################################################################
class BaseData():

    @property
    def dimord(self):
        return list(self._dimlabels.keys())

    @property
    def label(self):
        return self._dimlabels.get("label")

    @property
    def log(self):
        print(self._log_header + self._log)

    @log.setter
    def log(self, msg):
        if not isinstance(msg, str):
            raise SPWTypeError(log, varname="log", expected="str")
        prefix = "\n\n|=== {user:s}@{host:s}: {time:s} ===|\n\n\t"
        self._log += prefix.format(user=getpass.getuser(),
                                   host=socket.gethostname(),
                                   time=time.asctime()) + msg

    @property
    def mode(self):
        return self._mode
    
    @property
    def segments(self):
        return Indexer(map(self._get_segment, range(self._trialinfo.shape[0])),
                                self._trialinfo.shape[0]) \
                                if hasattr(self, "_trialinfo") else None
    
    @property
    def segmentlabel(self):
        return self._segmentlabel

    @segmentlabel.setter
    def segmentlabel(self, seglbl):
        if not isinstance(seglbl, str):
            raise SPWTypeError(seglbl, varname="segmentlabel", expected="str")
        options = ["trial", "other"]
        if seglbl not in options:
            raise SPWValueError("".join(opt + ", " for opt in options)[:-2],
                                varname="segmentlabel", actual=seglbl)
        if self._segmentlabel is None:
            self._segmentlabel = seglbl
            if seglbl == "trial":
                setattr(BaseData, "trial", property(lambda self: self.segments))
                setattr(BaseData, "trialinfo", property(lambda self: self._trialinfo))
                setattr(BaseData, "sampleinfo", property(lambda self: self._sampleinfo))
        else:
            if self._segmentlabel != seglbl:
                msg = "Cannot change `segmentlabel` property from " +\
                      "'{current:s}' to '{wanted}'. Please create new BaseData object"
                spw_warning(msg.format(current=str(self._segmentlabel), wanted=seglbl),
                            caller="SpykeWave core")

    @property
    def segmentshapes(self):
        return [(len(self.label), tinfo[1] - tinfo[0]) for tinfo in self._trialinfo] \
            if self.label else None

    @property
    def time(self, unit="s"):
        converter = {"h": 1/360, "min": 1/60, "s" : 1, "ms" : 1e3, "ns" : 1e9}
        if not isinstance(unit, str):
            raise SPWTypeError(unit, varname="unit", expected="str")
        if unit not in converter.keys():
            raise SPWValueError("".join(opt + ", " for opt in converter.keys())[:-2],
                                varname="unit", actual=unit)
        return [np.arange(start, end)*converter[unit]/self.samplerate \
                for (start, end) in self._sampleinfo] if hasattr(self, "samplerate") else None

    @property
    def version(self):
        return self._version

    # # Class creation
    # def __new__(cls, 
    #             filename=None,
    #             filetype=None,
    #             trialdefinition=None,
    #             label=None,
    #             segmentlabel=None):
    #     """
    #     Main SpykeWave data container
    #     """
    #     # print('here')
    #     import ipdb; ipdb.set_trace()
    #     # return object.__new__(cls, **kwargs)
    #     #                       # filename=None,
    #     #                       # filetype=None,
    #     #                       # trialdefinition=None,
    #     #                       # label=None,
    #     #                       # segmentlabel=None)
    #                           
    #     return super(BaseData, cls).__new__(cls)
    #     # return super(BaseData, cls).__new__(cls,
    #     #                                     filename=None,
    #     #                                     filetype=None,
    #     #                                     trialdefinition=None,
    #     #                                     label=None,
    #     #                                     segmentlabel=None)
        
    # Class customization
    def __init__(self,
                 filename=None,
                 filetype=None,
                 trialdefinition=None,
                 label=None,
                 segmentlabel=None):
        """
        Docstring
        """

        # import ipdb; ipdb.set_trace()

        # In case `BaseData` has been instantiated before, remove potentially
        # created dynamic properties
        if hasattr(self, "trialinfo"):
            delattr(self, "trial")
            delattr(self, "trialinfo")
            delattr(self, "sampleinfo")
        if hasattr(self, "hdr"):
            delattr(self, "hdr")
        if hasattr(self, "samplerate"):
            delattr(self, "samplerate")

        # Depending on contents of `filename`, class instantiation invokes I/O routines
        read_fl = True
        if filename is None:
            read_fl = False

        # Prepare necessary "global" parsing attributes
        self._dimlabels = OrderedDict()
        self._segmentlabel = None
        self._mode = "w"

        # Write version
        self._version = __version__

        # Write log-header information
        lhd = "\n\t\t>>> SpykeWave v. {ver:s} <<< \n\n" +\
              "Created: {timestamp:s} \n\n" +\
              "--- LOG ---"
        self._log_header = lhd.format(ver=__version__, timestamp=time.asctime())

        # Write initial log entry
        self._log = ""
        self.log = "Created BaseData object"

        # self._init_empty()

        # if read_fl:
        #     self.load(filename, filetype=filetype, label=label,
        #               trialdefinition=trialdefinition, segmentlabel=segmentlabel,
        #               out=self)

        # Finally call appropriate reading routine if filename was provided
        if read_fl:
            if label is None:
                label = "channel"
            if segmentlabel is None:
                segmentlabel = "trial"
            sw.load_data(filename, filetype=filetype, label=label,
                         trialdefinition=trialdefinition, segmentlabel=segmentlabel,
                         out=self)
        # else:
        #     self._init_empty()
            

    # def _init_empty(self):
    #     
    #     # In case `BaseData` has been instantiated before, remove potentially
    #     # created dynamic properties
    #     if hasattr(self, "trialinfo"):
    #         delattr(self, "trial")
    #         delattr(self, "trialinfo")
    #         delattr(self, "sampleinfo")
    #     if hasattr(self, "hdr"):
    #         delattr(self, "hdr")
    #     if hasattr(self, "samplerate"):
    #         delattr(self, "samplerate")

    # Helper function that leverages `ChunkData`'s getter routine to return a single segment
    def _get_segment(self, segno):
        return self._chunks[:, int(self._trialinfo[segno, 0]) : int(self._trialinfo[segno, 1])]

    # Wrapper that makes saving routine usable as class method
    def save(self, out_name, filetype=None, **kwargs):
        """
        Docstring that mostly points to ``save_data``
        """
        sw.save_data(out_name, self, filetype=filetype, **kwargs)
    
    # Legacy support
    def __repr__(self):
        return self.__str__()

    # Make class contents readable from the command line
    def __str__(self):

        # Get list of print-worthy attributes
        ppattrs = [attr for attr in self.__dir__() if not (attr.startswith("_") or attr == "log")]
        ppattrs = [attr for attr in ppattrs \
                   if not (inspect.ismethod(getattr(self, attr)) \
                           or isinstance(getattr(self, attr), Iterator))]
        ppattrs.sort()

        # Construct string for pretty-printing class attributes
        hdstr = "SpykeWave {diminfo:s}BaseData object with fields\n\n"
        ppstr = hdstr.format(diminfo="'" + "' x '".join(dim for dim in self.dimord) \
                             + "' " if self.dimord else "")
        maxKeyLength = max([len(k) for k in ppattrs])
        for attr in ppattrs:
            value = getattr(self, attr)
            if hasattr(value, 'shape'):            
                valueString = "[" + " x ".join([str(numel) for numel in value.shape]) \
                              + "] element " + str(type(value))
            elif isinstance(value, list):
                valueString = "{0} element list".format(len(value))
            elif isinstance(value, dict):
                msg = "dictionary with {nk:s}keys{ks:s}"
                keylist = value.keys()
                showkeys = len(keylist) < 7
                valueString = msg.format(nk=str(len(keylist)) + " " if not showkeys else "",
                                         ks=" '" + "', '".join(key for key in keylist) + "'" if showkeys else "")
            else:
                valueString = str(value)
            printString =  "{0:>" + str(maxKeyLength + 5) + "} : {1:}\n"
            ppstr += printString.format(attr, valueString)
        ppstr += "\nUse `.log` to see object history"
        return ppstr

##########################################################################################
class ChunkData():

    # Pre-allocate slots here - this class is *not* meant to be expanded
    # and/or monkey-patched later on
    __slots__ = ["_M", "_N", "_shape", "_size", "_nrows", "_data", "_rows"]

    @property
    def M(self):
        return self._M

    @property
    def N(self):
        return self._N

    @property
    def shape(self):
        return self._shape

    @property
    def size(self):
        return self._size
    
    # Class instantiation
    def __init__(self, chunk_list):
        """
        Docstring coming soon...

        Do not confuse chunks with segments: chunks refer to actual raw binary
        data-files on disk, thus, row- *and* col-numbers MUST match!
        """

        # First, make sure our one mandatary input argument does not contain
        # any unpleasant surprises
        if not isinstance(chunk_list, (list, np.ndarray)):
            raise SPWTypeError(chunk_list, varname="chunk_list", expected="array_like")

        # Do not use ``spw_array_parser`` to validate chunks to not force-load memmaps
        try:
            shapes = [chunk.shape for chunk in chunk_list]
        except:
            raise SPWTypeError(chunk_list[0], varname="chunk in chunk_list",
                               expected="2d-array-like")
        if np.any([len(shape) != 2 for shape in shapes]):
            raise SPWValueError(legal="2d-array", varname="chunk in chunk_list")

        # Get row number per input chunk and raise error in case col.-no. does not match up
        shapes = [chunk.shape for chunk in chunk_list]
        if not np.array_equal([shape[1] for shape in shapes], [shapes[0][1]]*len(shapes)):
            raise SPWValueError(legal="identical number of samples per chunk",
                                varname="chunk_list")
        nrows = [shape[0] for shape in shapes]
        cumlen = np.cumsum(nrows)

        # Create list of "global" row numbers and assign "global" dimensional info
        self._nrows = nrows
        self._rows = [range(start, stop) for (start, stop) in zip(cumlen - nrows, cumlen)]
        self._M = cumlen[-1]
        self._N = chunk_list[0].shape[1]
        self._shape = (self._M, self._N)
        self._size = self._M*self._N
        self._data = chunk_list

    # Compatibility
    def __len__(self):
        return self._size

    # The only part of this class that actually does something
    def __getitem__(self, idx):

        # Extract queried row/col from input tuple `idx`
        qrow, qcol = idx
        
        # Convert input to slice (if it isn't already) or assign explicit start/stop values
        if isinstance(qrow, numbers.Number):
            try:
                spw_scalar_parser(qrow, varname="row", ntype="int_like", lims=[0, self._M])
            except Exception as exc:
                raise exc
            row = slice(int(qrow), int(qrow + 1))
        elif isinstance(qrow, slice):
            start, stop = qrow.start, qrow.stop
            if qrow.start is None:
                start = 0
            if qrow.stop is None:
                stop = self._M
            row = slice(start, stop)
        else:
            raise SPWTypeError(qrow, varname="row", expected="int_like or slice")    
        
        # Convert input to slice (if it isn't already) or assign explicit start/stop values
        if isinstance(qcol, numbers.Number):
            try:
                spw_scalar_parser(qcol, varname="col", ntype="int_like", lims=[0, self._N])
            except Exception as exc:
                raise exc
            col = slice(int(qcol), int(qcol + 1))
        elif isinstance(qcol, slice):
            start, stop = qcol.start, qcol.stop
            if qcol.start is None:
                start = 0
            if qcol.stop is None:
                stop = self._N
            col = slice(start, stop)
        else:
            raise SPWTypeError(qcol, varname="col", expected="int_like or slice")

        # Make sure queried row/col are inside dimensional limits
        err = "value between {lb:s} and {ub:s}"
        if not(0 <= row.start < self._M) or not(0 < row.stop <= self._M):
            raise SPWValueError(err.format(lb="0", ub=str(self._M)),
                                varname="row", actual=str(row))
        if not(0 <= col.start < self._N) or not(0 < col.stop <= self._N):
            raise SPWValueError(err.format(lb="0", ub=str(self._N)),
                                varname="col", actual=str(col))

        # The interesting part: find out wich chunk(s) `row` is pointing at
        i1 = np.where([row.start in chunk for chunk in self._rows])[0].item()
        i2 = np.where([(row.stop - 1) in chunk for chunk in self._rows])[0].item()

        # If start and stop are not within the same chunk, data is loaded into memory
        if i1 != i2:
            data = []
            data.append(self._data[i1][row.start - self._rows[i1].start:, col])
            for i in range(i1 + 1, i2):
                data.append(self._data[i][:, col])
            data.append(self._data[i2][:row.stop - self._rows[i2].start, col])
            return np.vstack(data)

        # If start and stop are in the same chunk, return a view of the underlying memmap
        else:
            
            # Convert "global" row index to local chunk-based row-number (by subtracting offset)
            row = slice(row.start - self._rows[i1].start, row.stop - self._rows[i1].start)
            return self._data[i1][row,:][:,col]

##########################################################################################
class Indexer():

    __slots__ = ["_iterobj", "_iterlen"]
    
    def __init__(self, iterobj, iterlen):
        """
        Make an iterable object subscriptable using itertools magic
        """
        self._iterobj = iterobj
        self._iterlen = iterlen

    def __iter__(self):
        return self._iterobj

    def __getitem__(self, idx):
        if isinstance(idx, numbers.Number):
            try:
                spw_scalar_parser(idx, varname="idx", ntype="int_like",
                                  lims=[0, self._iterlen - 1])
            except Exception as exc:
                raise exc
            return next(islice(self._iterobj, idx, idx + 1))
        elif isinstance(idx, slice):
            start, stop = idx.start, idx.stop
            if idx.start is None:
                start = 0
            if idx.stop is None:
                stop = self._iterlen
            index = slice(start, stop, idx.step)
            if not(0 <= index.start < self._iterlen) or not (0 < index.stop <= self._iterlen):
                err = "value between {lb:s} and {ub:s}"
                raise SPWValueError(err.format(lb="0", ub=str(self._iterlen)),
                                    varname="idx", actual=str(index))
            return np.hstack(islice(self._iterobj, index.start, index.stop, index.step))
        elif isinstance(idx, (list, np.ndarray)):
            try:
                spw_array_parser(idx, varname="idx", ntype="int_like",
                                 lims=[0, self._iterlen], dims=1)
            except Exception as exc:
                raise exc
            return np.hstack([next(islice(self._iterobj, int(ix), int(ix + 1))) for ix in idx])
        else:
            raise SPWTypeError(idx, varname="idx", expected="int_like or slice")
    
    def __len__(self):
        return self._iterlen

    def __repr__(self):
        return self.__str__()
    
    def __str__(self):
        return "{} element iterable".format(self._iterlen)
