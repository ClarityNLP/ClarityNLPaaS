import configparser
import time
from os import getenv, environ, path

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session
from time import strftime, localtime
from os import environ
import logging, traceback
from pymongo import MongoClient

import sys

SCRIPT_DIR = path.dirname(__file__)
config = configparser.RawConfigParser()
config.read(path.join(SCRIPT_DIR, 'project.cfg'))

DEBUG = "DEBUG"
INFO = "INFO"
WARNING = "WARNING"
ERROR = "ERROR"
CRITICAL = "CRITICAL"
logger = None


def set_logger(l):
    global logger
    logger = l

    use_gunicorn_logger = environ.get('USE_GUNICORN', "true")
    print("use_gunicorn_logger", use_gunicorn_logger)
    if l and use_gunicorn_logger == "true":
        gunicorn_logger = logging.getLogger("gunicorn.error")
        logger.handlers = gunicorn_logger.handlers
        logger.setLevel(gunicorn_logger.level)


def log(obj=None, level=INFO, file=sys.stdout):
    if not obj:
        obj = ''

    if isinstance(obj, Exception):
        log("EXCEPTION: {}".format(repr(obj), level=ERROR))
        for t in traceback.format_tb(obj.__traceback__):
            lines = t.split('\n')
            for l in lines:
                if l.strip() == '':
                    continue
                log("     {}".format(l), level=ERROR)
        return

    repr_obj = repr(obj)
    if '\n' in repr_obj:
        for l in repr_obj.split('\n'):
            log(l, level=level)
        return

    if level == ERROR or level == CRITICAL:
        if file == sys.stdout:
            file = sys.stderr
    global logger

    if logger:
        message = repr_obj
        if level == DEBUG:
            logger.debug(message)
        elif level == WARNING:
            logger.warning(message)
        elif level == ERROR:
            logger.error(message)
        elif level == CRITICAL:
            logger.critical(message)
        else:
            logger.info(message)
    else:
        message = repr_obj
        the_time = strftime("%Y-%m-%d %H:%M:%S-%Z", localtime())
        print("[{}] {} in worker: {}".format(the_time, level, message))


def read_property(env_name, config_tuple):
    property_name = ''
    if getenv(env_name):
        property_name = environ.get(env_name)
    else:
        try:
            property_name = config.get(config_tuple[0], config_tuple[1])
        except Exception as ex:
            log(repr(ex))
    return property_name


def ensure_termination(url):
    """
    Ensure that the url ends with a '/' character.
    """

    if not url.endswith('/'):
        return url + '/'
    else:
        return url


_token = None
_token_time = None
_oauth = None

# Solr
solr_url = read_property('NLP_SOLR_URL', ('solr', 'url'))
solr_url = ensure_termination(solr_url)
solr_username = read_property('NLP_SOLR_USER', ('solr', 'username'))
solr_password = read_property('NLP_SOLR_PASSWORD', ('solr', 'password'))

# ClarityNLP
claritynlp_url = read_property('CLARITY_NLP_URL', ('claritynlp', 'url')).strip()
claritynlp_url = ensure_termination(claritynlp_url)
claritynlp_clientid = 'nlpass'
# claritynlp_scope = ['solr_api', 'nlp_api']
claritynlp_scope = 'nlp_api solr_api'
claritynlp_tokenurl = read_property('CLARITY_TOKEN_URL', ('claritynlp', 'token_url'))
claritynlp_clientsecret = read_property('CLARITY_NLP_SECRET', ('claritynlp', 'secret')).strip()

# Dev mode
development_mode = read_property('DEV_ENV', ('development', 'mode'))

# FHIR
cql_eval_url = read_property('CQL_EVAL_URL', ('fhir', 'cql_eval_url'))
print('cql_eval_url', cql_eval_url)
fhir_terminology_service_uri = read_property('FHIR_TERMINOLOGY_SERVICE_URI',
                                             ('fhir', 'fhir_terminology_service_uri'))
fhir_terminology_service_endpoint = read_property('FHIR_TERMINOLOGY_SERVICE_ENDPOINT',
                                                  ('fhir', 'fhir_terminology_service_endpoint'))
fhir_terminology_user_name = read_property('FHIR_TERMINOLOGY_USER_NAME',
                                           ('fhir', 'fhir_terminology_user_name'))
fhir_terminology_user_password = read_property('FHIR_TERMINOLOGY_USER_PASSWORD',
                                               ('fhir', 'fhir_terminology_user_password'))

custom_nlpql_s3_bucket = read_property('CUSTOM_S3_URL', ('custom', 's3_url'))
custom_nlpql_folder = read_property('CUSTOM_DIR', ('custom', 's3_folder'))

mongo_host = read_property('PAAS_MONGO_HOSTNAME', ('mongo', 'host'))
mongo_port = int(read_property('PAAS_MONGO_CONTAINER_PORT', ('mongo', 'port')))
mongo_db = read_property('PAAS_MONGO_DATABASE', ('mongo', 'db'))
mongo_working_index = read_property(
    'PAAS_MONGO_WORKING_INDEX', ('mongo', 'working_index'))
mongo_working_collection = read_property(
    'PAAS_MONGO_WORKING_COLLECTION', ('mongo', 'working_collection'))
mongo_username = read_property('PAAS_MONGO_USERNAME', ('mongo', 'username'))
mongo_password = read_property('PAAS_MONGO_PASSWORD', ('mongo', 'password'))


def app_token():
    if not claritynlp_clientsecret or len(claritynlp_clientsecret.strip()) == 0:
        return None, requests
    global _token
    global _token_time
    global _oauth
    expired = False
    try:
        # if len(claritynlp_clientsecret) > 5:
        #     display_secret = claritynlp_clientsecret[-4:]
        # else:
        #     display_secret = ''
        # log('claritynlpurl: ', claritynlp_url, ', clientid: ', claritynlp_clientid, ', scope: ', claritynlp_scope,
        #       ', tokenurl: ', claritynlp_tokenurl, ', clientsecret last 4 chars: ', display_secret)
        if _token and _token_time:
            total_time = time.time() - _token_time
            expired = abs(total_time) > abs(_token.get('expires_in', total_time + 1))
        if not _token or expired:
            _token_time = time.time()
            # client = BackendApplicationClient(client_id=claritynlp_clientid, scope=claritynlp_scope)
            # _oauth = OAuth2Session(client=client)
            # _token = _oauth.fetch_token(token_url=claritynlp_tokenurl, client_id=claritynlp_clientid,
            #                             client_secret=claritynlp_clientsecret)
            auth = HTTPBasicAuth(claritynlp_clientid, claritynlp_clientsecret)
            client = BackendApplicationClient(client_id=claritynlp_clientid, scope=claritynlp_scope)
            _oauth = OAuth2Session(client=client, scope=claritynlp_scope)
            _token = _oauth.fetch_token(token_url=claritynlp_tokenurl, auth=auth, client_secret=claritynlp_clientsecret)
            # _oauth = OAuth2Session(claritynlp_clientid, token=_token, scope=claritynlp_scope)
    except Exception as ex1:
        log(ex1, ERROR)
        _oauth = None
        _token = None
    if not _oauth:
        return None, requests
    return _token, _oauth


def mongo_client(host=None, port=None, username=None, password=None):
    if not host:
        host = mongo_host

    if not port:
        port = mongo_port

    if not username:
        username = mongo_username

    if not password:
        password = mongo_password

    # log('Mongo port: {}; host: {}'.format(port, host))
    if username and len(username) > 0 and password and len(password) > 0:
        # print('authenticated mongo')
        _mongo_client = MongoClient(host=host, port=port, username=username,
                                    password=password, socketTimeoutMS=15000, maxPoolSize=500,
                                    maxIdleTimeMS=30000)
    else:
        # print('unauthenticated mongo')
        _mongo_client = MongoClient(host, port)
    return _mongo_client
