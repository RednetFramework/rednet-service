from pkgutil import extend_path

try:
    import colorlog
    colorlog_installed = True
except ImportError:
    import logging
    colorlog_installed = False

__path__ = extend_path(__path__, __name__)

format = '%(filename)s %(asctime)s - %(name)s - %(levelname)s - %(message)s'
if not colorlog_installed:

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(format)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.setLevel(logging.DEBUG)

    logger.addHandler(handler)
else:
    logger = colorlog.getLogger(__name__)
    logger.setLevel(colorlog.DEBUG)

    handler = colorlog.StreamHandler()
    handler.setFormatter(colorlog.ColoredFormatter(
        log_colors={
            'DEBUG':    'thin',
            'INFO':     'light_cyan',
            'WARNING':  'yellow',
            'ERROR':    'red',
            'CRITICAL': 'bold_red',
        }
    ))
    logger.addHandler(handler)
