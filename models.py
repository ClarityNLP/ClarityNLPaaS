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


class ResultDisplayObject(pydantic.BaseModel):
    date: str
    result_content: str
    sentence: str
    highlights: list[str]
    start: list[int]
    end: list[int]


class NLPResult(pydantic.BaseModel):
    _id: str
    batch: str
    concept_code: str
    concept_code_system: str
    display_name: str
    end: int
    experiencer: str
    inserted_date: str
    job_id: int
    negation: str
    nlpql_feature: str
    owner: str
    phenotype_final: str
    pipeline_id: int
    pipeline_type: str
    report_date: str
    report_id: str
    report_type: str
    result_display: ResultDisplayObject
    section: str
    sentence: str
    solr_id: str
    source: str
    start: str
    subject: str
    temporality: str
    term: str
    text: str
    value: str

class DetailResponse(pydantic.BaseModel):
    detail: str

class DetailLocationResponse(DetailResponse):
    location: str