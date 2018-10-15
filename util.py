import configparser
from os import getenv, environ, path

SCRIPT_DIR = path.dirname(__file__)
config = configparser.RawConfigParser()
config.read(path.join(SCRIPT_DIR, 'project.cfg'))


def read_property(env_name, config_tuple):
    property_name = ''
    if getenv(env_name):
        property_name = environ.get(env_name)
    else:
        try:
            property_name = config.get(config_tuple[0], config_tuple[1])
        except Exception as ex:
            print(ex)
    return property_name

# Solr
solr_url = read_property('NLP_SOLR_URL', ('solr', 'url'))

# Mongo
mongo_host = read_property('NLP_MONGO_HOSTNAME', ('mongo', 'host'))
mongo_port = int(read_property('NLP_MONGO_CONTAINER_PORT', ('mongo', 'port')))

# ClarityNLP
claritynlp_url = read_property('CLARITY_NLP_URL', ('claritynlp', 'url'))
