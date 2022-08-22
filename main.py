'''Main function for FastAPI application'''

import logging

from collections import defaultdict

from fastapi import FastAPI, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from api import app_router
from models import CustomFormatter
from util import log_level

logger = logging.getLogger('main')
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

# ------------------ FastAPI variable ----------------------------------
app = FastAPI(title='NLPaaS Lite', version='0.0.1')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ================= App Validation Error Override ======================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    reformatted_message = defaultdict(list)
    for pydantic_error in exc.errors():
        loc, msg = pydantic_error["loc"], pydantic_error["msg"]
        filtered_loc = loc[1:] if loc[0] in ("body", "query", "path") else loc
        try:
            field_string = ".".join(filtered_loc)  # nested fields with dot-notation
        except TypeError:  # Handles malformed JSON (extra comma)
            return JSONResponse({'detail': 'Something was malformed in your request body'}, 400)
        reformatted_message[field_string].append(msg)

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder(
            {"detail": "Invalid request", "errors": reformatted_message}
        ),
    )


# ================ Router inclusion from src directory =================
app.include_router(app_router)

# =========================== Custom OpenAPI ===========================

def custom_openapi():
    '''Defines the custom OpenAPI schema handling'''
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="NLPaaS Lite",
        version="0.0.1",
        description="This is a custom Open API Schema to align with NLPaaS Lite's API endpoints",
        routes=app.routes,
    )

    openapi_schema["paths"]["/job/register_nlpql"]["post"]["requestBody"]["content"] = {"text/plain": {"schema": {}}}
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi