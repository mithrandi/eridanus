import os

from epsilon.extime import FixedOffset


DEBUG = bool(os.environ.get('ERIDANUS_DEV'))

timezone = FixedOffset(2, 0)

ENCODING = 'utf-8'
