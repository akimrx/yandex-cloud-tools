import os
import logging

LOGLEVEL = logging.INFO

if not os.path.exists('logs'):
    os.mkdir('logs')

logformat = '[%(asctime)s] [%(levelname)s] %(message)s'
logging.basicConfig(level=LOGLEVEL,
    format=logformat,
    datefmt='%d/%b/%y %H:%M:%S', 
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)