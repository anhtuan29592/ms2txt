"""
Reading metastock files.
"""

import struct
import re
import math
import traceback
import sys
import os
import os.path
from .utils import fmsbin2ieee, float2date, float2time

class DataFileInfo(object):
    """
    I represent a metastock data describing a single symbol
    Each symbol has a number (file_num). To read the quotes we need to read
    two files: a <file_num>.DAT file with the tick data and a <file_num>.DOP
    file describing what columns are in the DAT file
    @ivar file_num: symbol number
    @ivar num_fields: number of columns in DAT file
    @ivar stock_symbol: stock symbol
    @ivar stock_name: full stock name
    @ivar time_frame: tick time frame (f.e. 'D' means EOD data)
    @ivar first_date: first tick date
    @ivar last_date: last tick date
    @ivar columns: list of columns names
    """
    file_num = None
    num_fields = None
    bit_fields = None
    bits = None
    stock_symbol = None
    stock_name = None
    time_frame = None
    first_date = None
    last_date = None

    reg = re.compile('\"(.+)\",.+', re.IGNORECASE)
    columns = None

    def _load_columns(self):
        """
        Read columns names from the DOP file
        """
        filename = 'F%d.DOP' % self.file_num
        try:
          file_handle = open(filename, 'r')
        except IOError:
          filename = 'F%d.dop' % self.file_num
          file_handle = open(filename, 'r')
        lines = file_handle.read().split()
        file_handle.close()
        num_fields = 0
        self.bits = []
        if self.bit_fields:
          for bit_position in range(8):
            if ((1 << bit_position) & self.bit_fields) > 0:
              self.bits.append(1)
              num_fields = num_fields + 1
            else:
              self.bits.append(0)
          self.num_fields = num_fields
        while len(lines) > self.num_fields:
          lines.pop()
        assert(len(lines) == self.num_fields)
        self.columns = []
        for line in lines:
            match = self.reg.search(line)
            colname = match.groups()[0]
            self.columns.append(colname)

    class Column(object):
        """
        This is a base class for classes reading metastock data for a specific
        columns. The read method is called when reading a decode the column
        value
        @ivar dataSize: number of bytes is the data file that is used to store
                        a single value
        @ivar name: column name
        """
        dataSize = 4
        name = None

        def __init__(self, name):
            self.name = name

        def read(self, bytes):
            """Read and return a column value"""

        def format(self, value):
            """
            Return a string containing a value returned by read method
            """
            return str(value)

    class DateColumn(Column):
        """A date column"""
        def read(self, bytes):
            """Convert from MBF to date string"""
            return float2date(fmsbin2ieee(bytes))

        def format(self, value):
            if value is not None:
                return "%02d%02d%02d" % (value.year, value.month, value.day)
            return DataFileInfo.Column.format(self, value)

    class TimeColumn(Column):
        """A time column"""
        def read(self, bytes):
            """Convert read bytes from MBF to time string"""
            return float2time(fmsbin2ieee(bytes))

        def format(self, value):
            if value is not None:
                return "%02d%02d%02d" % (value.year, value.month, value.day)
            return DataFileInfo.Column.format(self, value)

    class FloatColumn(Column):
        """
        A float column
        @ivar precision: round floats to n digits after the decimal point
        """
        precision = 2

        def read(self, bytes):
            """Convert bytes containing MBF to float"""
            return fmsbin2ieee(bytes)

        def format(self, value):
            return ("%0."+str(self.precision)+"f") % value

    class IntColumn(Column):
        """An integer column"""
        def read(self, bytes):
            """Convert MBF bytes to an integer"""
            return int(fmsbin2ieee(bytes))

    # we map a metastock column name to an object capable reading it
    knownMSColumns = {
        'DATE': DateColumn('Date'),
        'TIME': TimeColumn('Time'),
        'OPEN': FloatColumn('Open'),
        'HIGH': FloatColumn('High'),
        'LOW': FloatColumn('Low'),
        'CLOSE': FloatColumn('Close'),
        'VOL': IntColumn('Volume'),
        'OI': IntColumn('Oi'),
    }
    unknownColumnDataSize = 4    # assume unknown column data is 4 bytes long

    max_recs = 0
    last_rec = 0

    def load_candles(self):
        """
        Load metastock DAT file and write the content
        to a text file
        """
        file_handle = None
        outfile = None
        try:
            filename = 'F%d.DAT' % self.file_num
            if not os.path.exists(filename):
              filename = 'F%d.MWD' % self.file_num # XMASTER
            file_handle = open(filename, 'rb')
            self.max_recs = struct.unpack("H", file_handle.read(2))[0]
            self.last_rec = struct.unpack("H", file_handle.read(2))[0]

            # not sure about this, but it seems to work
            file_handle.read((self.num_fields - 1) * 4)

            #print "Expecting %d candles in file %s. num_fields : %d" % \
            #    (self.last_rec - 1, filename, self.num_fields)

            if os.environ.get('MS2TXT_CSV_PATH'):
                outfile = open('%s%s.CSV' % (os.environ.get('MS2TXT_CSV_PATH'), self.stock_symbol), 'w')
            else:
                outfile = open('%s.CSV' % self.stock_symbol, 'w')
            # write the header line, for example:
            #"Name","Date","Time","Open","High","Low","Close","Volume","Oi"
            outfile.write('"Name"')
            columns = []
            for ms_col_name in self.columns:
                column = self.knownMSColumns.get(ms_col_name)
                if self.bits[self.columns.index(ms_col_name)] == 0:
                    1
                elif column is not None:
                    outfile.write(',"%s"' % column.name.replace('"', '""'))
                columns.append(column) # we append None if the column is unknown
            outfile.write('\n')

            if os.environ.get('MS2TXT_YYYYMMDD'):
                yyyymmdd = int(os.environ.get('MS2TXT_YYYYMMDD'))
            else:
                yyyymmdd = 0
            perform_write = True

            # we have (self.last_rec - 1) candles to read
            for _ in xrange(self.last_rec - 1):
                for col in columns:
                    if col is None: # unknown column?
                        # ignore this column
                        file_handle.read(self.unknownColumnDataSize)
                    else:
                        # read the column data
                        bytes = file_handle.read(col.dataSize)
                        # decode the data
                        value = col.read(bytes)
                        # format it
                        value = col.format(value)
                        if col.__class__ == DataFileInfo.DateColumn:
                            perform_write = (int(value) >= yyyymmdd)
                            if perform_write:
                                outfile.write('"%s"' % self.stock_name)
                        if perform_write:
                            outfile.write(',%s' % value)
                if perform_write:
                    outfile.write('\n')
        finally:
            if outfile is not None:
                outfile.close()
            if file_handle is not None:
                file_handle.close()

    def convert2ascii(self):
        """
        Load Metastock data file and output the data to text file.
        """
        print "Processing %s (fileNo %d)" % (self.stock_symbol, self.file_num)
        try:
            #print self.stock_symbol, self.file_num
            self._load_columns()
            #print self.columns
            self.load_candles()
        except Exception:
            print "Error while converting symbol", self.stock_symbol
            traceback.print_exc()

class MSEMasterFile(object):
    """
    Metastock extended index file
    @ivar stocks: list of DataFileInfo objects
    """
    stocks = None

    def _read_file_info(self, file_handle):
        """
        read the entry for a single symbol and return a DataFileInfo
        describing it
        @parm file_handle: emaster file handle
        @return: DataFileInfo instance
        """
        dfi = DataFileInfo()
        file_handle.read(2)
        dfi.file_num = struct.unpack("B", file_handle.read(1))[0]
        file_handle.read(3)
        dfi.num_fields = struct.unpack("B", file_handle.read(1))[0]
        dfi.bit_fields = struct.unpack("B", file_handle.read(1))[0]
        file_handle.read(3)
        dfi.stock_symbol = file_handle.read(14).strip('\x00')
        file_handle.read(7)
        dfi.stock_name = file_handle.read(16).strip('\x00')
        if dfi.stock_name.find('\x00') > 0:
          dfi.stock_name = dfi.stock_name[0:dfi.stock_name.find('\x00')]
        file_handle.read(12)
        dfi.time_frame = struct.unpack("c", file_handle.read(1))[0]
        file_handle.read(3)
        dfi.first_date = float2date(struct.unpack("f", \
                                                   file_handle.read(4))[0])
        file_handle.read(4)
        dfi.last_date = float2date(struct.unpack("f", \
                                                  file_handle.read(4))[0])
        file_handle.read(116)
        if dfi.first_date is None or dfi.last_date is None:
          print >> sys.stderr, ["Bad dates", dfi.stock_symbol, dfi.stock_name]
          return None
        return dfi

    def __init__(self, filename, precision=None):
        """
        The whole file is read while creating this object
        @param filename: name of the file to open (usually 'EMASTER')
        @param precision: round floats to n digits after the decimal point
        """
        if precision is not None:
            DataFileInfo.FloatColumn.precision = precision
        file_handle = open(filename, 'rb')
        files_no = struct.unpack("H", file_handle.read(2))[0]
        last_file = struct.unpack("H", file_handle.read(2))[0]
        file_handle.read(188)
        self.stocks = []
        #print files_no, last_file
        while files_no > 0:
            dfi = self._read_file_info(file_handle)
            if dfi is not None:
              self.stocks.append(dfi)
            files_no -= 1
        file_handle.close()

    def list_all_symbols(self):
        """
        Lists all the symbols from metastock index file and writes it
        to the output
        """
        for stock in self.stocks:
            print "symbol: %s, name: %s, file number: %s" % \
                (stock.stock_symbol, stock.stock_name, stock.file_num)

    def output_ascii(self, all_symbols, symbols):
        """
        Read all or specified symbols and write them to text
        files (each symbol in separate file)
        @param all_symbols: when True, all symbols are processed
        @type all_symbols: C{bool}
        @param symbols: list of symbols to process
        """
        for stock in self.stocks:
            if all_symbols or (stock.stock_symbol in symbols):
                stock.convert2ascii()

class MSXMasterFile(object):
    """
    XMASTER format via http://meta-all.sourceforge.net/MS%20File%20Format.html
    @ivar stocks: list of DataFileInfo objects
    """
    stocks = None

    def _read_file_info(self, file_handle):
        """
        read the entry for a single symbol and return a DataFileInfo
        describing it
        @parm file_handle: emaster file handle
        @return: DataFileInfo instance
        """
        dfi = DataFileInfo()
        file_handle.read(1)
        dfi.stock_symbol = file_handle.read(15)
        if dfi.stock_symbol.find('\x00') > 0:
          dfi.stock_symbol = dfi.stock_symbol[0:dfi.stock_symbol.find('\x00')]
        dfi.stock_name = file_handle.read(46)
        if dfi.stock_name.find('\x00') > 0:
          dfi.stock_name = dfi.stock_name[0:dfi.stock_name.find('\x00')]
        dfi.time_frame = struct.unpack("c", file_handle.read(1))[0]
        file_handle.read(2)
        dfi.file_num = struct.unpack("h", file_handle.read(2))[0]
        file_handle.read(3)
        dfi.bit_fields = struct.unpack("b", file_handle.read(1))[0]
        file_handle.read(9)
        dfi.last_date = struct.unpack("i", file_handle.read(4))[0]
        file_handle.read(20)
        dfi.first_date = struct.unpack("i", file_handle.read(4))[0]
        file_handle.read(4+4+4+30)
        return dfi

    def __init__(self, filename, precision=None):
        """
        The whole file is read while creating this object
        @param filename: name of the file to open (usually 'EMASTER')
        @param precision: round floats to n digits after the decimal point
        """
        if precision is not None:
            DataFileInfo.FloatColumn.precision = precision
        file_handle = open(filename, 'rb')
        file_handle.read(1+1+2+6)
        files_no = struct.unpack("h", file_handle.read(2))[0]
        file_handle.read(2+2+2+2+130)
        self.stocks = []
        while files_no > 0:
            self.stocks.append(self._read_file_info(file_handle))
            files_no -= 1
        file_handle.close()

    def list_all_symbols(self):
        """
        Lists all the symbols from metastock index file and writes it
        to the output
        """
        for stock in self.stocks:
            print "symbol: %s, name: %s, file number: %s" % \
                (stock.stock_symbol, stock.stock_name, stock.file_num)

    def output_ascii(self, all_symbols, symbols):
        """
        Read all or specified symbols and write them to text
        files (each symbol in separate file)
        @param all_symbols: when True, all symbols are processed
        @type all_symbols: C{bool}
        @param symbols: list of symbols to process
        """
        for stock in self.stocks:
            if all_symbols or (stock.stock_symbol in symbols):
                stock.convert2ascii()


class MSMasterFile(object):
    """
    XMASTER format via http://meta-all.sourceforge.net/MS%20File%20Format.html
    @ivar stocks: list of DataFileInfo objects
    """
    stocks = None

    def _read_file_info(self, file_handle):
        """
        read the entry for a single symbol and return a DataFileInfo
        describing it
        @parm file_handle: emaster file handle
        @return: DataFileInfo instance
        """
        dfi = DataFileInfo()

        dfi.file_num = struct.unpack("B", file_handle.read(1))[0]
        file_handle.read(6)
        dfi.stock_name = file_handle.read(16)
        if dfi.stock_name.find('\x00') > 0:
            dfi.stock_name = dfi.stock_name[0:dfi.stock_name.find('\x00')]
        file_handle.read(2)
        dfi.first_date = struct.unpack("i", file_handle.read(4))[0]
        dfi.last_date = struct.unpack("i", file_handle.read(4))[0]
        file_handle.read(3)
        dfi.stock_symbol = file_handle.read(14)
        if dfi.stock_symbol.find('\x00') > 0:
          dfi.stock_symbol = dfi.stock_symbol[0:dfi.stock_symbol.find('\x00')]
        file_handle.read(3)
        return dfi

    def __init__(self, filename, precision=None):
        """
        The whole file is read while creating this object
        @param filename: name of the file to open (usually 'EMASTER')
        @param precision: round floats to n digits after the decimal point
        """
        if precision is not None:
            DataFileInfo.FloatColumn.precision = precision
        file_handle = open(filename, 'rb')
        files_no = struct.unpack("H", file_handle.read(2))[0]
        file_handle.read(51)
        self.stocks = []
        #print files_no, last_file
        while files_no > 0:
            dfi = self._read_file_info(file_handle)
            if dfi is not None:
              self.stocks.append(dfi)
            files_no -= 1
        file_handle.close()

    def list_all_symbols(self):
        """
        Lists all the symbols from metastock index file and writes it
        to the output
        """
        for stock in self.stocks:
            print "symbol: %s, name: %s, file number: %s" % \
                (stock.stock_symbol, stock.stock_name, stock.file_num)

    def output_ascii(self, all_symbols, symbols):
        """
        Read all or specified symbols and write them to text
        files (each symbol in separate file)
        @param all_symbols: when True, all symbols are processed
        @type all_symbols: C{bool}
        @param symbols: list of symbols to process
        """
        for stock in self.stocks:
            if all_symbols or (stock.stock_symbol in symbols):
                stock.convert2ascii()
