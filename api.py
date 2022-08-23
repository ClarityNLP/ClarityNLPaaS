'''File for API routes in the application'''

from fastapi import APIRouter, Body

import logging
import typing

from worker import add_custom_nlpql, run_job
from models import DetailLocationResponse, DetailResponse, RunNLPQLPostBody, CustomFormatter, NLPResult

from util import log_level

logger = logging.getLogger('api')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(CustomFormatter())
logger.addHandler(ch)

uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.name = 'api'
logger.handlers = uvicorn_access_logger.handlers

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


@app_router.post('/job/register_nlpql', response_model=typing.Union[DetailLocationResponse, DetailResponse])
def register_nlpql(nlpql: str = Body(...)):
    '''
    Saves NLPQL to the filesystem for use at `/job/{nlpql_library}`
    '''

    return add_custom_nlpql(nlpql=nlpql)


@app_router.post('/job/{nlpql_library}', response_model=list[NLPResult])
def run_nlpql(nlpql_library: str, post_body: RunNLPQLPostBody):
    '''
    Runs NLPQL library given in path against patient and documents given in post body
    '''
    temp_output = run_job(nlpql_library, post_body)
    logger.info('Run NLPQL Output:')
    logger.info(temp_output)
    return temp_output
