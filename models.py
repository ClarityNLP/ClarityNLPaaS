"""File for holding models for necessary operation of API"""

import logging
import pydantic
import typing


nlpql_example = """// Phenotype library name
phenotype "Syphilis_Test" version "1";

include ClarityCore version "1.0" called ClarityNLP;


termset syphilis_test_unstructured_terms: [
    "syphilis", "rash"
];


define final syphilis_test_unstructured:
    ClarityNLP.TermFinder({
		termset: [syphilis_test_unstructured_terms]
	});
"""


class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;21m"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    red = "\x1b[31m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format_str = "{asctime}   {levelname:8s} --- [{process:2d}] {name}: {message}"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%m/%d/%Y %I:%M:%S %p", style="{")
        return formatter.format(record)


class FHIRAuthObject(pydantic.BaseModel):
    auth_type: str
    token: str


class FHIRConnectionInfo(pydantic.BaseModel):
    service_url: str
    auth: typing.Optional[FHIRAuthObject] = None


class RunNLPQLReports(pydantic.BaseModel):
    id: str
    report_id: str
    source: str
    report_date: str
    subject: str
    report_type: str
    report_text: str


class RunNLPQLPostBody(pydantic.BaseModel):
    patient_id: str
    date: str | None = None
    fhir: typing.Optional[FHIRConnectionInfo] = None
    reports: typing.Optional[list[RunNLPQLReports]] = None

    class Config:
        schema_extra = {
            "example": {
                "patient_id": "12345",
                "date": "2025",
                "fhir": {"service_url": "https://example.org/fhir/", "auth": {"auth_type": "Bearer", "token": "112233445566"}},
                "reports": [
                    {
                        "id": "cde69f20-0a9b-4755-aaca-2330de486f6d",
                        "report_id": "cde69f20-0a9b-4755-aaca-2330de486f6d",
                        "source": "Super Test Document Set",
                        "report_date": "2022-06-24T15:02:43.378272Z",
                        "subject": "12345",
                        "report_type": "Example Doc",
                        "report_text": "sepsis and on vent",
                    }
                ],
            }
        }


class ResultDisplayObject(pydantic.BaseModel):
    date: str | None
    result_content: str | None
    sentence: str | None
    highlights: list | None
    start: list[int] | None
    end: list[int] | None


class NLPResult(pydantic.BaseModel):
    _id: str | None
    _ids_1: str | None
    batch: str | None
    concept_code: str | None
    concept_code_system: str | None
    context_type: str | None
    display_name: str | None
    education_level: str | None
    employment_status: str | None
    end: int | None
    experiencer: str | None
    housing: str | None
    immigration_status: str | None
    inserted_date: str | None
    job_date: str | None
    job_id: int | None
    languages: str | None
    negation: str | None
    nlpql_feature: str | None
    nlpql_features_1: str | None
    owner: str | None
    phenotype_final: str | None
    phenotype_id: int | None
    pipeline_id: int | None
    pipeline_type: str | None
    raw_definition_text: str | None
    religion: str | None
    report_date: str | None
    report_id: str | None
    report_type: str | None
    report_text: str | None
    result_display: ResultDisplayObject
    section: str | None
    section_header: str | None
    section_text: str | None
    sentence: str | None
    sexual_orientation: str | None
    solr_id: str | None
    source: str | None
    start: str | None
    subject: str | None
    temporality: str | None
    term: str | None
    text: str | None
    tuple: str | None
    value: str | dict | None

    class Config:
        schema_extra = {
            "example": {
                "_id": "62ffaa5c89a7fbdf159477c8",
                "batch": "0",
                "concept_code": "",
                "concept_code_system": "",
                "display_name": "syphilis_test_unstructured",
                "end": 58,
                "experiencer": "Patient",
                "inserted_date": "2022-08-19 15:21:00.320000",
                "job_id": 72,
                "negation": "Affirmed",
                "nlpql_feature": "syphilis_test_unstructured",
                "owner": "claritynlp",
                "phenotype_final": "True",
                "pipeline_id": 115,
                "pipeline_type": "TermFinder",
                "report_date": "2022-01-14",
                "report_id": "13000118",
                "report_type": "Note",
                "result_display": {
                    "date": "2022-01-14",
                    "result_content": "The medical provider is concerned about secondary syphilis and orders a rapid point of care treponemal test in the office which is positive.",
                    "sentence": "The medical provider is concerned about secondary syphilis and orders a rapid point of care treponemal test in the office which is positive.",
                    "highlights": ["syphilis"],
                    "start": [50],
                    "end": [58],
                },
                "section": "UNKNOWN",
                "sentence": "The medical provider is concerned about secondary syphilis and orders a rapid point of care treponemal test in the office which is positive.",
                "solr_id": "13000118",
                "source": "FHIR",
                "start": "50",
                "subject": "46529",
                "temporality": "Recent",
                "term": "syphilis",
                "text": "syphilis",
                "value": "True",
            }
        }


class DetailResponse(pydantic.BaseModel):
    detail: str


class DetailLocationResponse(DetailResponse):
    location: str
