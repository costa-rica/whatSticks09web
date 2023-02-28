import os
import json
from dotenv import load_dotenv

load_dotenv()


with open(os.path.join(os.environ.get('CONFIG_PATH'), os.environ.get('CONFIG_FILE_NAME'))) as config_file:
    config = json.load(config_file)


class ConfigBase:

    def __init__(self):

        self.SECRET_KEY = config.get('SECRET_KEY')
        self.PROJ_ROOT_PATH = os.environ.get('PROJ_ROOT_PATH')
        self.PROJ_DB_PATH = os.environ.get('PROJ_DB_PATH')
        self.DESTINATION_PASSWORD = config.get('DESTINATION_PASSWORD')


class ConfigLocal(ConfigBase):

    def __init__(self):
        super().__init__()

    DEBUG = True
            

class ConfigDev(ConfigBase):

    def __init__(self):
        super().__init__()

    DEBUG = True
            

class ConfigProd(ConfigBase):

    def __init__(self):
        super().__init__()

    DEBUG = False