# configuration file for pyepg


__all__ = ['TV_DATEFORMAT', 'TV_TIMEFORMAT', 'TV_DATETIMEFORMAT' ]


# The file format version number. It must be updated when incompatible
# changes are made to the file format.
EPG_VERSION       = 5


TV_DATEFORMAT     = '%e-%b' # Day-Month: 11-Jun
TV_TIMEFORMAT     = '%H:%M' # Hour-Minute 14:05
TV_DATETIMEFORMAT = '%A %b %d %I:%M %p' # Thursday September 24 8:54 am


# variables needed for compat.py

DEBUG    = 1                            # debug level
encoding = 'latin-1'                    # encoding
LOCALE   = 'latin-1'                    # locale setting

