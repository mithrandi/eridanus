import pytz
import dateutil.parser

from epsilon.extime import FixedOffset, Time


# XXX: This is probably incomplete, also it doesn't support overloaded names
# such as "EST" in Australia.  I wonder how to implement something like that.
TZINFOS = {
    'WET':  FixedOffset( 0,   0),  # Western European
    'WEST': FixedOffset( 1,   0),  # Western European Summer
    'BST':  FixedOffset( 0,   0),  # British Summer
    'ART':  FixedOffset(-3,   0),  # Argentina
    'BRT':  FixedOffset(-3,   0),  # Brazil
    'BRST': FixedOffset(-2,   0),  # Brazil Summer
    'NST':  FixedOffset(-3, -30),  # Newfoundland Standard
    'NDT':  FixedOffset(-2, -30),  # Newfoundland Daylight
    'AST':  FixedOffset(-4,   0),  # Atlantic Standard
    'ADT':  FixedOffset(-3,   0),  # Atlantic Daylight
    'CLT':  FixedOffset(-4,   0),  # Chile
    'CLST': FixedOffset(-3,   0),  # Chile Summer
    'EST':  FixedOffset(-5,   0),  # Eastern Standard
    'EDT':  FixedOffset(-4,   0),  # Eastern Daylight
    'CST':  FixedOffset(-6,   0),  # Central Standard
    'CDT':  FixedOffset(-5,   0),  # Central Daylight
    'MST':  FixedOffset(-7,   0),  # Mountain Standard
    'MDT':  FixedOffset(-6,   0),  # Mountain Daylight
    'PST':  FixedOffset(-8,   0),  # Pacific Standard
    'PDT':  FixedOffset(-7,   0),  # Pacific Daylight
    'AKST': FixedOffset(-9,   0),  # Alaska Standard
    'AKDT': FixedOffset(-8,   0),  # Alaska Daylight
    'HST':  FixedOffset(-10,  0),  # Hawaii Standard
    'HAST': FixedOffset(-10,  0),  # Hawaii-Aleutian Standard
    'HADT': FixedOffset(-9,   0),  # Hawaii-Aleutian Daylight
    'SST':  FixedOffset(-12,  0),  # Samoa Standard
    'WAT':  FixedOffset( 1,   0),  # West Africa
    'CET':  FixedOffset( 1,   0),  # Central European
    'CEST': FixedOffset( 2,   0),  # Central European Summer
    'MET':  FixedOffset( 1,   0),  # Middle European
    'MEZ':  FixedOffset( 1,   0),  # Middle European
    'MEST': FixedOffset( 2,   0),  # Middle European Summer
    'MESZ': FixedOffset( 2,   0),  # Middle European Summer
    'EET':  FixedOffset( 2,   0),  # Eastern European
    'EEST': FixedOffset( 3,   0),  # Eastern European Summer
    'CAT':  FixedOffset( 2,   0),  # Central Africa
    'SAST': FixedOffset( 2,   0),  # South Africa Standard
    'EAT':  FixedOffset( 3,   0),  # East Africa
    'MSK':  FixedOffset( 3,   0),  # Moscow
    'MSD':  FixedOffset( 4,   0),  # Moscow Daylight
    'IST':  FixedOffset( 5,  30),  # India Standard
    'SGT':  FixedOffset( 8,   0),  # Singapore
    'KST':  FixedOffset( 9,   0),  # Korea Standard
    'JST':  FixedOffset( 9,   0),  # Japan Standard
    'GST':  FixedOffset( 10,  0),  # Guam Standard
    'NZST': FixedOffset( 12,  0),  # New Zealand Standard
    'NZDT': FixedOffset( 13,  0)}  # New Zealand Daylight


def format(dt, formatString):
    """
    Format a C{datetime.datetime} object according to C{formatString}.

    @rtype: C{unicode}
    """
    return unicode(dt.strftime(formatString), 'ascii')


def now(timezoneName):
    """
    Get the current time in the timezone named C{timezoneName}.

    @rtype: C{datetime.datetime}
    """
    return Time().asDatetime(tzinfo=pytz.timezone(timezoneName))


def convert(timeString, timezoneName, defaultTimezoneName):
    """
    Convert C{timeString} to the timezone named C{timezoneName}.

    @rtype: C{datetime.datetime}
    """
    timezone = pytz.timezone(timezoneName)
    dt = _parse(timeString)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=pytz.timezone(defaultTimezoneName))
    return dt.astimezone(timezone)



def _parse(timeString):
    return dateutil.parser.parse(timeString, tzinfos=TZINFOS)



def parse(timeString):
    return Time.fromDatetime(_parse(timeString))
