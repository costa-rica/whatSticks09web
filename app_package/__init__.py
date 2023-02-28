from flask import Flask
from app_package.config import ConfigLocal, ConfigDev, ConfigProd
import os
import logging
from logging.handlers import RotatingFileHandler
from pytz import timezone
from datetime import datetime


from ws09_models import login_manager

if os.environ.get('CONFIG_TYPE')=='local':
    config = ConfigLocal()
    print('- Personalwebsite/__init__: Development - Local')
elif os.environ.get('CONFIG_TYPE')=='dev':
    config = ConfigDev()
    print('- Personalwebsite/__init__: Development')
elif os.environ.get('CONFIG_TYPE')=='prod':
    config = ConfigProd()
    print('- Personalwebsite/__init__: Configured for Production')


if not os.path.exists(os.path.join(os.environ.get('PROJ_ROOT_PATH'),'logs')):
    os.makedirs(os.path.join(os.environ.get('PROJ_ROOT_PATH'), 'logs'))

# timezone 
def timetz(*args):
    return datetime.now(timezone('Europe/Paris') ).timetuple()

logging.Formatter.converter = timetz

formatter = logging.Formatter('%(asctime)s:%(name)s:%(message)s')
formatter_terminal = logging.Formatter('%(asctime)s:%(filename)s:%(name)s:%(message)s')

logger_init = logging.getLogger('__init__')
logger_init.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(os.path.join(os.environ.get('PROJ_ROOT_PATH'),'logs','__init__.log'), mode='a', maxBytes=5*1024*1024,backupCount=2)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter_terminal)

stream_handler_tz = logging.StreamHandler()

logger_init.addHandler(file_handler)
logger_init.addHandler(stream_handler)

logging.getLogger('werkzeug').setLevel(logging.DEBUG)
logging.getLogger('werkzeug').addHandler(file_handler)

logger_init.info(f'--- Starting API Endpoint Tester ---')


def create_app(config_for_flask = config):
    app = Flask(__name__)   
    app.config.from_object(config_for_flask)
    login_manager.init_app(app)

    from app_package.main.routes import main

    app.register_blueprint(main)

    return app