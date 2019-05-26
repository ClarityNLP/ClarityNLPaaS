import configparser
import time
from os import getenv, environ, path

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

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
fhir_terminology_service_uri = read_property('FHIR_TERMINOLOGY_SERVICE_URI',
                                             ('fhir', 'fhir_terminology_service_uri'))
fhir_terminology_service_endpoint = read_property('FHIR_TERMINOLOGY_SERVICE_ENDPOINT',
                                                  ('fhir', 'fhir_terminology_service_endpoint'))
fhir_terminology_user_name = read_property('FHIR_TERMINOLOGY_USER_NAME',
                                           ('fhir', 'fhir_terminology_user_name'))
fhir_terminology_user_password = read_property('FHIR_TERMINOLOGY_USER_PASSWORD',
                                               ('fhir', 'fhir_terminology_user_password'))

def app_token():
    if not claritynlp_clientsecret or len(claritynlp_clientsecret.strip()) == 0:
        return None, requests
    global _token
    global _token_time
    global _oauth
    expired = False
    try:
        print('claritynlpurl: ', claritynlp_url)
        print('clientid: ', claritynlp_clientid)
        print('scope: ', claritynlp_scope)
        print('tokenurl: ', claritynlp_tokenurl)
        print('clientsecret: ', claritynlp_clientsecret)
        if _token_time:
            total_time = time.time() - _token_time
            expired = abs(total_time) > abs(_token['expires_in'])
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
        print(ex1)
        _oauth = None
        _token = None
    if not _oauth:
        return None, requests
    return _token, _oauth
