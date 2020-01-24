import os
import logging

from logging.handlers import RotatingFileHandler


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# FILEOUT
file_handler = RotatingFileHandler(filename='snapshoter.log', maxBytes=10240, backupCount=-10)
file_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%D %H:%M:%S'))
file_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)

# STDOUT
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%D %H:%M:%S'))
stream_handler.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(stream_handler)