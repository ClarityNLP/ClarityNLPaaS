'''File for API routes in the application'''

from fastapi import APIRouter, Body

import logging

from worker import add_custom_nlpql, run_job
from models import RunNLPQLPostBody, CustomFormatter

from util import log_level

logger = logging.getLogger('api')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

if log_level.lower() == 'debug':
    logger.info('Logging level is being set to DEBUG')
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
else:
    logger.info('Logging level is at INFO')

app_router = APIRouter()

@app_router.get('/')
def return_root():
    return {'detail': 'Welcome to Clarity NLPaaS Lite. Swagger UI is available at /docs.'}


@app_router.post('/job/register_nlpql')
def register_nlpql(nlpql: str = Body(...)):
    return add_custom_nlpql(nlpql=nlpql)


@app_router.post('/job/{nlpql_library}')
def run_nlpql(nlpql_library: str, post_body: RunNLPQLPostBody):
    return run_job(nlpql_library, post_body)
