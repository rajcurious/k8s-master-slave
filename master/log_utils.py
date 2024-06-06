import logging
#Creating handlers
c_handler = logging.StreamHandler()
f_handler = logging.FileHandler('file.log')
f_handler.setLevel(level=logging.INFO)
c_handler.setLevel(level=logging.DEBUG)

# Create formatters and add it to handlers
c_format = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
f_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
c_handler.setFormatter(c_format)
f_handler.setFormatter(f_format)

def get_logger(name):
    logger = logging.getLogger(name)
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)
    return logger