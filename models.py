'''File for holding models for necessary operation of API'''
import logging
import pydantic
import typing


class CustomFormatter(logging.Formatter):

    grey = "\x1b[38;21m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = '{asctime}   {levelname:8s} --- [{process:2d}] {name}: {message}'

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, '%m/%d/%Y %I:%M:%S %p', style='{')
        return formatter.format(record)


class FHIRAuthObject(pydantic.BaseModel):
    auth_type: str
    token: str


class FHIRConnectionInfo(pydantic.BaseModel):
    service_url: str
    auth: typing.Optional[FHIRAuthObject] = None


class RunNLPQLPostBody(pydantic.BaseModel):
    patient_id: str
    fhir: FHIRConnectionInfo
    reports: typing.Optional[list] = None
