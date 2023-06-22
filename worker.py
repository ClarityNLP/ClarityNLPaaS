'''Worker file for handling operations from the API'''

import os
import logging
import requests
import time
import base64
import json
import re

from fastapi.responses import JSONResponse

from fhir.resources.documentreference import DocumentReference

import util
import models

logger = logging.getLogger('worker')
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(models.CustomFormatter())
logger.addHandler(ch)

if util.log_level.lower() == 'debug':
    logger.info('Logging level is being set to DEBUG')
    logger.setLevel(logging.DEBUG)
    ch.setLevel(logging.DEBUG)
    logger.addHandler(ch)
else:
    logger.info('Logging level is at INFO')

def add_custom_nlpql(nlpql):
    if not os.path.exists('./nlpql'):
        os.makedirs('./nlpql')

    success, test_json = submit_test(nlpql)
    if not success:
        test_json['detail'] = "Failed to upload invalid NLPQL."
        return JSONResponse(test_json, status_code=400)

    phenotype = test_json['phenotype']
    if not phenotype:
        logger.error('NLPQL uploaded is missing phenotype declaration')
        return JSONResponse({'detail': 'NLPQL missing phenotype declaration.'}, status_code=400)

    name = phenotype['name']
    version = phenotype['version']

    if not name or len(name) == 0:
        return JSONResponse({'detail': 'Phenotype declaration missing name'}, status_code=400)

    if not version or len(version) == 0:
        return JSONResponse({'detail': 'Phenotype declaration missing version'}, status_code=400)

    nlpql_name = f"{'_'.join(name.split(' '))}_v{version.replace('.', '-')}"
    filename = f'./nlpql/{nlpql_name}.nlpql'
    with open(filename, 'w') as outfile:
        outfile.write(nlpql)

    return JSONResponse({
        'detail': 'Your NLPQL has been saved, you can run it via the URL found in the location key of this response',
        'location': f"/job/{nlpql_name}"
    }, status_code=201, headers={'Location': f"/job/{nlpql_name}"})


def submit_test(nlpql):
    """
    Testing ClarityNLP job
    """

    url = util.clarity_nlp_api_url + 'nlpql_tester'
    logger.info(f'URL from submit_test: "{url}"')

    response = requests.post(url, data=nlpql)

    if response.status_code == 200:
        data = response.json()
        if 'success' in data and not data['success']:
            logger.error(f'Error in testing NLPQL: {data["error"]}')
            return False, data['error']
        if 'valid' in data and not data['valid']:
            logger.info(f"Testing NLPQL was a success: {data['valid']}")
            return False, data['valid']
        return True, data
    else:
        logger.error(f"Error in testing uploaded NLPQL, response returned status code: {response.status_code}")
        logger.error(response.reason)
        return False, {
            'success': False,
            'status_code': response.status_code,
            'reason': str(response.reason),
            'valid': False
        }


def load_reports_from_fhir(fhir_url, patient_id, fhir_auth: dict = None, idx=0):
    reports = []

    if fhir_url[-1] != '/':
        fhir_url += '/'

    try:
        if fhir_auth:
            r = requests.get(fhir_url + f'DocumentReference?patient={patient_id}', headers=fhir_auth)
        else:
            r = requests.get(fhir_url + f'DocumentReference?patient={patient_id}')
        res_data = r.json()
        links = res_data.get('link', [])
        entry = res_data.get('entry', [])
        reports = list(map(lambda x: x.get('resource', {}), entry))

        next_idx = idx + 1
        if next_idx < len(links):
            next_link = links[next_idx]
            next_url = next_link.get('url')
            if next_url:
                reports.extend(load_reports_from_fhir(next_url, fhir_auth, patient_id, idx=next_idx))

    except Exception as ex:
        logger.error(f'Exception during getting DocumentReferences from FHIR: {ex}')

    return reports


def get_file(file_path):
    """
    Getting required file based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    return content


def convert_document_references_to_reports(doc_refs: list) -> list:
    output_list = []
    for resource in doc_refs:
        resource = DocumentReference(**resource)
        output_object = {
            "id": resource.id,
            "report_id": resource.id,
            "source": "FHIR",
            "report_date": resource.date.strftime('%Y-%m-%d'),
            "subject": resource.subject.reference.split('/')[-1] if resource.subject.reference[0:7].lower() == 'patient' else resource.subject.reference,
            "report_type": resource.type.coding[0].display,
            "report_text": base64.b64decode(resource.content[0].attachment.data).decode("utf-8")
        }
        output_list.append(output_object)
    return output_list


def submit_job(nlpql_json):
    """
    Submitting ClarityNLP job
    """

    url = util.clarity_nlp_api_url + 'phenotype'
    logger.info(f'URL from submit_job: "{url}"')

    logger.info(f"POSTing phenotype: {nlpql_json.get('name')}")

    response = requests.post(url, json=nlpql_json)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data and not data['success']:
            logger.error(data['error'])
            return False, data['error']
        return True, data
    else:
        logger.error(f'Submitting the job to ClarityNLP return the response code {response.status_code} and reason {response.reason}')
        return False, response.reason


def get_results(job_id: int, name="NLPAAS Job"):
    """
    Reading Results from API endpoint
    """
    logger.info(f'** JOB ID {job_id} **')

    # Wating for job completion
    time.sleep(10.0)

    # /job_results/<int:job_id>/phenotype?clearResults=true to delete from Mongo after collecting
    if util.clear_results.lower() == 'true':
        url = util.clarity_nlp_api_url + f'job_results/{job_id}/phenotype?clearResults=true'
    else:
        url = util.clarity_nlp_api_url + f'job_results/{job_id}/phenotype'

    results = requests.get(url).text

    logger.debug('Phenotype Results from NLP API:')
    logger.debug(results)

    try:
        if len(results) == 0:
            logger.info(f'No results found for job {job_id}')
            return [], True

        results = [result.strip('\r') for result in results.split('\n')]
        logger.info(f'Total results for {name}: {len(results)}')

        return results, True

    except Exception as ex:
        logger.error(f'Error in get_results: {ex}')
        return [], False


def clean_output(results: list, reports: list[dict]) -> list:
    """
    Clean up results and format into final return list of dictionaries
    """

    header = results[0].split(',')
    results = [re.sub(r'"([^"]*)"', lambda x: x.group(0).replace(',','^'), result).split(',') for result in results[1:]]

    cleaned_results = []
    for result in results:
        if len(result) != len(header):
            continue

        cleaned_result_dict = {header[i]: item for i, item in enumerate(result)}
        cleaned_result_display_string = cleaned_result_dict['result_display'].replace('^', ',').strip('"').replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null').replace('""', '\\"')
        cleaned_result_display_string = re.sub('([A-Za-z]+)[\"`]([A-Za-z]+)', r'\1'r'\2', cleaned_result_display_string)
        try:
            cleaned_result_dict['result_display'] = json.loads(cleaned_result_display_string)
        except json.decoder.JSONDecodeError:
            cleaned_result_dict['result_display'] = json.loads(cleaned_result_display_string.replace('\\"', '"'))
        cleaned_result_dict['sentence'] = cleaned_result_dict['sentence'].replace('"', '').replace('^', ',')
        try:
            cleaned_result_dict['start'] = int(cleaned_result_dict['start'])
        except KeyError:
            pass
        try:
            cleaned_result_dict['end'] = int(cleaned_result_dict['end'])
        except KeyError:
            pass
        try:
            cleaned_result_dict['job_id'] = int(cleaned_result_dict['job_id'])
        except KeyError:
            pass
        try:
            cleaned_result_dict['pipeline_id'] = int(cleaned_result_dict['pipeline_id'])
        except KeyError:
            pass
        try:
            cleaned_result_dict['tuple'] = cleaned_result_dict['tuple'].replace('^', ',')
        except KeyError:
            pass

        report_of_interest = list(filter(lambda x: x['report_id'] == cleaned_result_dict['report_id'], reports))[0]
        cleaned_result_dict['report_text'] = report_of_interest['report_text']

        if 'phenotype_id' not in cleaned_result_dict or cleaned_result_dict['phenotype_id'] == '':
            cleaned_result_dict['phenotype_id'] = None

        if None in cleaned_result_dict['result_display']['highlights']:
            cleaned_result_dict['result_display']['highlights'] = ['' if not x else x for x in cleaned_result_dict['result_display']['highlights']]

        cleaned_results.append(cleaned_result_dict)

        logger.debug('Cleaned Result:')
        logger.debug(cleaned_result_dict)

    return cleaned_results


def run_job(nlpql_library_name, data, nlpql=None):
    """
    Main function to run jobs
    """
    results = list()
    start = time.time()
    # check for fhir
    fhir_data_service_uri = None

    if isinstance(data, models.RunNLPQLPostBody):
        fhir = data.fhir
        fhir_data_service_uri = fhir.service_url
    else:
        # TODO: need to figure outh FHIR Server Auth Stuff, most likely will just need RC-API to pass DocRefs
        pass

    logger.info(f'Running NLPQL against Patient ID {data.patient_id}')

    if not data.reports:
        if fhir.auth:
            fhir_auth_dict = {'Authorization': f'{fhir.auth.auth_type} {fhir.auth.token}'}
            data.reports = load_reports_from_fhir(fhir_url=fhir_data_service_uri, patient_id=data.patient_id, fhir_auth=fhir_auth_dict)
        else:
            data.reports = load_reports_from_fhir(fhir_url=fhir_data_service_uri, patient_id=data.patient_id)

    # Getting the NLPQL from disk
    if not nlpql_library_name and not nlpql:
        return JSONResponse({'detail': 'Please pass in NLPQL text or a valid NLPQL file name'}, status_code=400)
    elif nlpql_library_name:
        try:
            nlpql = get_file(f'./nlpql/{nlpql_library_name}.nlpql')
        except FileNotFoundError:
            return JSONResponse({'detail': 'NLPQL Library not found, please post the NLPQL library before running'}, status_code=404)

    # Validating the input object
    success, nlpql_json = submit_test(nlpql)
    if not success:
        logger.error(f'Something went wrong with testing the NLPQL!')
        logger.error(nlpql_json)
        return JSONResponse(nlpql_json, status_code=400)

    # Adding in the reports to the JSON to be submitted
    try:
        # This is checking if the reports are of type DocumentReference and need to be converted to the correct object schema
        assert all([item['resourceType'] == 'DocumentReference' for item in data.reports])
        nlpql_json['reports'] = convert_document_references_to_reports(data.reports)
    except AssertionError:
        # data.reports is of the correct type and can be passed on to be submitted as is
        nlpql_json['reports'] = data.reports

    logger.debug('NLPQL JSON:')
    logger.debug(nlpql_json)

    # Submitting the job
    job_success, job_info = submit_job(nlpql_json)
    if not job_success:
        return JSONResponse({'detail': f'Could not submit job to NLP API, it returned a reason of: {job_info}'}, status_code=500)

    # Getting the results of the Job
    job_id = int(job_info['job_id'])
    results, got_results = get_results(job_id, name=nlpql_json.get('name'))

    logger.info(f"Run Time = {time.time() - start}")
    if not results:
        return results
    if not got_results:
        return JSONResponse({'detail': 'There was an error in get_results, see logs for full output', 'results': results}, status_code=500)

    return clean_output(results, reports=nlpql_json['reports'])
