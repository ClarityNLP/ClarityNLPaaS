import base64
import datetime
import json
import os
import re
import tempfile
import time
import uuid
from string import printable

import dateparser
import requests
from bson.json_util import dumps
from flask import Response
from tika import parser

import util
from util import log


def get_document_set(source):
    return {
        "alias": "",
        "arguments": [],
        "concept": "",
        "declaration": "documentset",
        "description": "",
        "funct": "createDocumentSet",
        "library": "ClarityNLP",
        "name": "Docs",
        "named_arguments": {
            "query": "source:{}".format(source)
        },
        "values": [],
        "version": ""
    }


def get_headers(token):
    if not token:
        headers = {
            'Content-type': 'application/json'
        }
    else:
        headers = {
            'Content-type': 'application/json',
            'Authorization': '{} {}'.format(token['token_type'], token['access_token'])
        }
    # log(json.dumps(headers, indent=4))
    return headers


def get_text(url, headers=None, key=None, base64_encoded=True):
    txt = ''
    response = requests.get(url, headers=headers, verify=False)
    if not headers:
        headers = {}
    headers['Authorization'] = 'hidden'
    # log(url, headers)
    log('get_text')
    log(response.status_code)

    if response.status_code != 200:
        log(response.content)
        return ''
    else:
        log('SUCCESS get_text')

    if key:
        raw_data_json = response.json()
        raw_data = raw_data_json[key]
    else:
        raw_data = response.content

    if base64_encoded:
        raw_data = base64.b64decode(raw_data)

    new_file, file_name = tempfile.mkstemp()
    os.write(new_file, raw_data)
    os.close(new_file)

    with open(file_name, 'rb'):
        try:
            content = parser.from_file(file_name)
            if 'content' in content:
                t = content['content']
            else:
                log('No content from file {}'.format(file_name))
                return ''
            safe_text = str(t)
            safe_text = safe_text.encode('utf-8', errors='ignore')
            safe_text = safe_text.decode("utf-8")
            txt = ''.join(char for char in safe_text if char in printable)

        except Exception as ex1:
            log(ex1)
    os.remove(file_name)
    return txt


def upload_reports(data, access_token=None):
    """
    Uploading reports with unique source
    """

    url = util.solr_url + 'update?commit=true&commitWithin=10000'
    log('URL from upload_reports: "{0}"'.format(url))

    print('SOLR url: ' + url)

    # Generating a source_id
    rand_uuid = uuid.uuid1()
    source_id = str(rand_uuid)

    payload = list()
    report_list = list()
    nlpaas_id = 1
    fhir_resource = False

    # print('**DATA**')
    # print(json.dumps(data, indent=4))

    for report in data['reports']:
        report_id = '{}_{}'.format(source_id, str(nlpaas_id))
        json_body = {
            "report_type": "ClarityNLPaaS Document",
            "id": report_id,
            "report_id": report_id,
            "source": source_id,
            "nlpaas_id": str(nlpaas_id),
            "subject": "ClarityNLPaaS Subject",
            "report_date": "1970-01-01T00:00:00Z",
            'original_report_id': ''
        }
        if type(report) == str:
            json_body["report_text"] = report
        else:
            resource_type = ''
            if 'resource' in report:
                report_resource = report.get('resource')
                report_resource['fullUrl'] = report.get('fullUrl')
                report = report_resource

            if 'resourceType' in report:
                resource_type = report['resourceType']

            report_date = None
            if 'created' in report:
                report_date = dateparser.parse(report['created'])
            if not report_date and 'indexed' in report:
                report_date = dateparser.parse(report['indexed'])
            if report_date:
                # The 'report_date' variable is a python 'datetime' object.
                # For Solr ingest, need to:
                #     1) convert to UTC
                #     2) format as Solr wants it
                utc_report_date = report_date.astimezone(tz=datetime.timezone.utc)
                json_body['report_date'] = utc_report_date.strftime('%Y-%m-%dT%H:%M:%SZ')

            if 'subject' in report:
                if 'reference' in report['subject']:
                    subject = report['subject']['reference']
                else:
                    subject = str(report['subject'])
                if '/' in subject:
                    # subject usually returned as 'Patient/12345' or similar
                    subject = subject.split('/')[-1]
                json_body['subject'] = subject

            if 'id' in report:
                json_body['original_report_id'] = str(report['id'])

            if 'type' in report:
                if 'coding' in report['type'] and len(report['type']['coding']) > 0:
                    coded_type = report['type']['coding'][0]
                    if 'display' in coded_type:
                        json_body['report_type'] = coded_type['display']

            if resource_type == 'DocumentReference' or resource_type == 'DiagnosticReport':
                fhir_resource = True
                txt = ''
                # log('** REPORT **')
                # log(report)
                if 'content' in report:
                    for c in report['content']:
                        attachment = c.get('attachment', None)
                        if attachment:
                            content_type = attachment.get('contentType', 'text/plain')
                            report_data = attachment.get('data', None)
                            if content_type and report_data:
                                decoded_txt = base64.b64decode(report_data).decode("utf-8")
                                if content_type == 'application/pdf':
                                    if 'url' in c['attachment']:
                                        url = attachment.get('url')
                                        types = ['application/json+fhir', content_type]
                                        txt = ''
                                        for t in list(set(types)):
                                            if txt == '':
                                                if access_token:
                                                    headers = {
                                                        'Accept': t,
                                                        'Authorization': 'Bearer {}'.format(access_token)
                                                    }
                                                else:
                                                    headers = {
                                                        'Accept': t
                                                    }
                                                if 'json' in t:
                                                    txt = get_text(url, headers, key='content')
                                                else:
                                                    txt = get_text(url, headers)
                                elif 'xml' in content_type or 'html' in content_type:
                                    clean_txt = re.sub('<[^<]+?>', '', decoded_txt)
                                    txt += clean_txt
                                    txt += '\n'
                                else:
                                    txt += decoded_txt
                                    txt += '\n'

                            elif 'data' in c['attachment']:
                                decoded_txt = base64.b64decode(report_data).decode("utf-8")
                                txt += decoded_txt
                                txt += '\n'

                json_body["report_text"] = txt
            else:
                json_body["report_text"] = str(report)
        if len(json_body["report_text"]) > 0:
            payload.append(json_body)
            report_list.append(report_id)
            nlpaas_id += 1

    log('{} total documents'.format(len(payload)))
    # log('** PAYLOAD **', util.INFO)
    # log(payload, util.INFO)
    if len(payload) > 0:
        token, oauth = util.app_token()
        log('uploading solr docs...')
        response = requests.post(url, headers=get_headers(token), data=json.dumps(payload, indent=4), verify=False)
        if response.status_code == 200:
            the_time = 0
            while True:
                log('checking for solr upload...')
                data = dict()
                data['query'] = "*:*"
                data['params'] = {
                    'wt': 'json'
                }
                data['filter'] = 'source:"{}"'.format(source_id)
                doc_results = 0
                try:
                    post_data = json.dumps(data, indent=4)
                    response = requests.post((util.solr_url + '/select'), headers=get_headers(token), data=post_data,
                                             verify=False)
                    # log(response.text)
                    res = response.json().get('response', None)
                    if res:
                        doc_results = int(res.get('numFound', 0))
                except Exception as ex:
                    log(ex, util.ERROR)
                    log("unable to query docs", util.ERROR)

                if doc_results > 0:
                    log("documents uploaded {}".format(doc_results), util.INFO)
                    break

                the_time += 1
                time.sleep(1)

                if the_time > 15:
                    log("documents not yet loaded in 15 sec", util.ERROR)
                    break

            return True, source_id, report_list, fhir_resource, payload
        else:
            log(response.content)
            return False, response.reason, report_list, fhir_resource, payload
    else:
        return True, "All documents were empty or invalid, or no documents were passed in.", report_list, \
               fhir_resource, payload


def delete_report(source_id):
    """
    Deleting reports based on generated source
    """
    url = util.solr_url + 'update?commit=true'
    log('URL from delete_report: "{0}"'.format(url))

    data = '<delete><query>source:%s</query></delete>' % source_id

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=json.dumps(data, indent=4), verify=False)
    if response.status_code == 200:
        return True, response.reason
    else:
        return False, response.reason


def get_reports(source_id):
    """
    Get reports based on generated source
    """
    url = '{}/select?indent=on&q=source:{}&wt=json&rows=1000'.format(util.solr_url, source_id)

    token, oauth = util.app_token()
    response = requests.get(url, headers=get_headers(token), verify=False)
    if response.status_code == 200:
        res = response.json()['response']
        if not res:
            res = {
                'docs': []
            }
        return True, res['docs']
    else:
        return False, {'reason': response.reason}


def get_file(file_path):
    """
    Getting required file based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    return content


def get_nlpql(file_path):
    return get_file(file_path)


def get_json(file_path):
    """
    Getting required form based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    return content


def submit_job(nlpql_json):
    """
    Submitting ClarityNLP job
    """

    url = util.claritynlp_url + 'phenotype?background=false'
    log('URL from submit_job: "{0}"'.format(url))

    phenotype_string = json.dumps(nlpql_json)
    log("POSTing phenotype:")
    log(nlpql_json.get('name'))
    log("")

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=phenotype_string, verify=False)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                log(data['error'], util.ERROR)
                return False, data['error']
        # log("\n\nJob Response:\n")
        # log(data)
        return True, data
    else:
        log(response.status_code)
        log(response.reason)
        return False, response.reason


def submit_test(nlpql):
    """
    Testing ClarityNLP job
    """

    url = util.claritynlp_url + 'nlpql_tester'
    log('URL from submit_test: "{0}"'.format(url))

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=nlpql)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                log(data['error'], util.ERROR)
                return False, data['error']
        if 'valid' in data:
            if not data['valid']:
                log(data['valid'])
                return False, data['valid']
#         log("\n\nJob Response:\n")
#         log(data)
        return True, data
    else:
        log(response.status_code)
        log(response.reason)
        return False, {
            'success': False,
            'status_code': response.status_code,
            'reason': str(response.reason),
            'valid': False
        }


def add_custom_nlpql(nlpql):
    try:
        os.makedirs('./nlpql/custom/')
    except OSError as ex:
        log('custom directory already exists', util.ERROR)

    success, test_json = submit_test(nlpql)
    if not success:
        test_json['message'] = "Failed to upload invalid NLPQL."
        return test_json

    phenotype = test_json['phenotype']
    if not phenotype:
        return {
            'message': 'NLPQL missing phenotype declaration.'
        }
    name = phenotype['name']
    version = phenotype['version']

    if not name or len(name) == 0:
        return {
            'message': 'Phenotype declaration missing name'
        }

    if not version or len(version) == 0:
        return {
            'message': 'Phenotype declaration missing version'
        }
    nlpql_name = 'custom_{}_v{}'.format('_'.join(name.split(' ')), version.replace('.', '-'))
    filename = './nlpql/custom/{}.nlpql'.format(nlpql_name)
    with open(filename, 'w') as the_file:
        the_file.write(nlpql)

    return {
        'message': "Your job is callable via the endpoint '/job/custom/{}'".format(nlpql_name)
    }


def has_active_job(data):
    """
    DoS Protection by allowing user to have only one active job
    """
    # TODO: Query Luigi and see if the user has any current active job
    # If active job is present return
    return False


def get_results(job_id: int, source_data=None, report_ids=None, return_only_if_complete=False, patient_id=-1,
                name="NLPAAS Job"):
    log('** JOB ID**')
    log(job_id)
    """
    Reading Results from Mongo
    TODO use API endpoint
    """
    if not source_data:
        source_data = list()
    if not report_ids:
        report_ids = list()

    # Checking if it is a dev box
    status = "status/%s" % job_id
    url = util.claritynlp_url + status
    log('URL from get_results: "{0}"'.format(url))

    # Polling for job completion
    while True:
        time.sleep(3.0)

        token, oauth = util.app_token()
        r = oauth.get(url)

        if r.status_code != 200:
            return Response(
                json.dumps({'message': 'Could not query job status from NLP API. Reason: ' + r.reason}, indent=4),
                status=500,
                mimetype='application/json'), False

        try:
            status = r.json()["status"]
        except Exception as ex1:
            log(ex1, util.ERROR)
        if status == "COMPLETED":
            break
        if return_only_if_complete:
            break

    if return_only_if_complete and status != "COMPLETED":
        return '''
            {
                "job_completed": false,
                "job_id":{},
                "status":{}
            }
        '''.format(job_id, status), False

    time.sleep(3)

    # /phenotype_paged_results/<int:job_id>/<string:phenotype_final_str>
    """
    Submitting ClarityNLP job
    """
    results = list()
    final_list = list()
    n = 0
    r_formatted = ''
    while n < 10:
        results = list()
        url = "{}phenotype_paged_results/{}/{}".format(util.claritynlp_url, job_id, 'true')
        url2 = "{}phenotype_paged_results/{}/{}".format(util.claritynlp_url, job_id, 'false')

        response = oauth.get(url)
        response2 = oauth.get(url2)

        if response.status_code == 200:
            results.extend(response.json()['results'])
        if response2.status_code == 200:
            results.extend(response2.json()['results'])
        if len(results) > 0 and status == 'COMPLETED':
            break
        else:
            time.sleep(2.0)
            n += 1
    try:
        log('')
        log('total results for {}: {}'.format(name, len(results)))
        log('')
        log('')
        if len(results) == 0:
            return '''
                        "success":"true",
                        "message":"No results found for job id {}"
                    '''.format(job_id), False
        for r in results:
            # log('** REPORT (R)**', util.INFO)
            # log(r, util.INFO)
            r_formatted = json.dumps(r, indent=4)
            report_id = r['report_id']
            source = r['source']

            # Three types of result objects 'r' to handle:
            # 1) Result objects from ClarityNLP, computed via NLPQL
            #       These have been ingested into Solr, static
            #       All the expected fields present
            # 2) Result objects temporarily loaded into Solr via JSON blob
            #        The JSON blob is POSTed to NLPaaS
            #        The doc_index and source fields constructed differently
            #            from normal Solr ingest process
            # 3) Result objects obtained from FHIR server via CQL call
            #        CQLExecutionTask returns this data
            #        No underlying source document at all, so no report_text

            pipeline_type = r['pipeline_type'].lower()
            if 'cqlexecutiontask' == pipeline_type:
                # no source docs, data obtained via CQL query
                r['report_text'] = ''
                r['report_type'] = r.get('resourceType', 'Unknown')
                final_list.append(r)
                continue

            if len(report_ids) > 0 and report_id not in report_ids:
                continue

            # compute the doc_index encoded in the source field
            try:
                doc_index = int(report_id.replace(source, '').replace('_', '')) - 1
            except ValueError as ve:
                doc_index = -1
                log("non-integer source index", util.ERROR)
                log(ve, util.ERROR)
                log(r_formatted)

            if doc_index == -1 and patient_id != -1:
                r['report_text'] = ''
            elif len(source_data) > 0 and doc_index < len(source_data):
                source_doc = source_data[doc_index]
                r['report_text'] = source_doc['report_text']
            else:
                r['report_text'] = r['sentence']
            final_list.append(r)

        result_string = dumps(final_list)
        return result_string, True
    except Exception as ex:
        log(ex, util.ERROR)
        log(r_formatted)
        return '''
            "success":"false",
            "message":{}
        '''.format(str(ex)), False


def clean_output(data, report_list=None, return_null_results=False):
    """
    Function to clean output JSON
    """
    if not report_list:
        report_list = list()
    data = json.loads(data)
    report_dictionary = {x['report_id']: x for x in report_list}
    report_ids = list(report_dictionary.keys())
    matched_reports = list()

    # iterate through to check for report_ids that are empty and assign report count from original report_list
    for obj in data:
        report_id = obj["report_id"].split('_')
        if len(report_id) > 1:
            nlpaas_array_id = report_id[1]
            if obj["report_id"] in report_ids:
                orig_report = report_dictionary[obj["report_id"]]
                obj.update({
                    'nlpaas_report_list_id': nlpaas_array_id,
                    'original_report_id': orig_report['original_report_id']
                })
                matched_reports.append(obj["report_id"])
    # return null response for reports with no results
    for report in report_list:
        item = report['report_id']
        if item in matched_reports:
            continue
        if return_null_results:
            item_id = item.split('_')
            if len(item_id) > 1:
                nlpaas_array_id = int(item_id[1])
                data_object = report
                data_object['nlpaas_report_list_id'] = nlpaas_array_id
                data_object['nlpql_feature'] = 'null'
                data.append(data_object)

    # keys = ['_id', 'experiencer', 'report_id', 'source', 'phenotype_final', 'temporality', 'subject', 'concept_code',
    #         'report_type', 'inserted_date', 'negation', 'solr_id', 'end', 'start', 'report_date', 'batch',
    #         'nlpaas_id', 'owner', 'pipeline_id']

    # for k in keys:
    #     for obj in data:
    #         obj.pop(k, None)

    return json.dumps(data, indent=4, sort_keys=True)


def worker(job_file_path, data, synchronous=True, return_null_results=False, nlpql=''):
    """
    Main worker function
    """
    results = list()
    start = time.time()
    # check for fhir
    fhir_data_service_uri = ''
    fhir_auth_type = ''
    fhir_auth_token = ''
    fhir_auth_id_token = ''
    fhir_auth_patient = ''
    fhir_auth_expires_in = -1
    fhir_auth_scope = ''
    fhir_client_id = ''
    fhir_scope = ''
    fhir_redirect_uri = ''
    fhir_key = ''
    fhir_registration_uri = ''
    fhir_authorize_uri = ''
    fhir_token_uri = ''
    patient_id = -1
    encounter_id = -1
    try:
        fhir_version_str = str(data.get('fhirVersion', '3'))
        if "3" in fhir_version_str:
            fhir_version = 'STU3'
        elif "2" in fhir_version_str:
            fhir_version = 'DSTU2'
        elif "4" in fhir_version_str:
            fhir_version = 'R4'
        else:
            fhir_version = "Unknown"
    except Exception as fv_ex:
        log(fv_ex)
        fhir_version = 'STU3'

    if 'fhir' in data:
        fhir = data['fhir']
        if 'state' in fhir:
            fhir_state = fhir.get('state')
            fhir_client_id = fhir_state.get('clientId')
            fhir_scope = fhir_state.get('scope')
            fhir_data_service_uri = fhir_state.get('serverUrl')
            fhir_redirect_uri = fhir_state.get('redirectUri')
            if 'tokenResponse' in fhir_state:
                token_response = fhir_state['tokenResponse']
            elif 'auth' in fhir_state:
                token_response = fhir_state['auth']
            else:
                token_response = dict()
            if token_response:
                fhir_auth_token = token_response.get('access_token')
                fhir_auth_patient = token_response.get('patient')
                fhir_auth_scope = token_response.get('scope')
                fhir_auth_id_token = token_response.get('id_token')
                fhir_auth_type = token_response.get('token_type')
                fhir_auth_expires_in = token_response.get('expires_in')
            fhir_key = fhir_state.get('key')
            fhir_registration_uri = fhir_state.get('registrationUri')
            fhir_authorize_uri = fhir_state.get('authorizeUri')
            fhir_token_uri = fhir_state.get('tokenUri')
        else:
            fhir_data_service_uri = fhir.get('serviceUrl')

            if 'auth' in fhir:
                auth = fhir['auth']
                if 'type' in auth:
                    fhir_auth_type = auth['type']
                if 'token' in auth:
                    fhir_auth_token = auth['token']
    else:
        fhir = data

    if 'patient' in fhir:
        patient = fhir['patient']
        if 'id' in patient:
            patient_id = patient['id']
    elif 'patient_id' in fhir:
        patient_id = fhir['patient_id']
    elif 'patient_id' in data:
        patient_id = data['patient_id']
    elif 'patient' in data:
        patient = data['patient']
        if 'id' in patient:
            patient_id = patient['id']

    if 'encounter' in fhir:
        encounter = fhir['encounter']
        if 'id' in encounter:
            encounter_id = encounter['id']
    elif 'encounter_id' in fhir:
        encounter_id = fhir['encounter_id']
    elif 'encounter_id' in data:
        encounter_id = data['encounter_id']

    log('patient_id {}'.format(patient_id))
    source_id = data.get('source_id', 'UNKNOWN')
    reports = data.get('reports', [])

    if reports and len(reports) > 0:
        status, source_id, report_ids, is_fhir_resource, report_payload = upload_reports(data,
                                                                                         access_token=fhir_auth_token)
        if not status:
            return Response(json.dumps({'message': 'Could not upload reports to Solr. Reason: ' + source_id}, indent=4),
                            status=500,
                            mimetype='application/json')
    else:
        report_payload = list()
        report_ids = list()

    # Getting the nlpql from disk
    if not job_file_path or len(job_file_path) == 0:
        if not nlpql or len(nlpql) == 0:
            return Response(json.dumps('{"message":"Please pass in NLPQL text or a valid path"}',
                                       indent=4, sort_keys=True), status=400, mimetype='application/json')
    else:
        nlpql = get_nlpql(job_file_path)

    # Validating the input object
    success, nlpql_json = submit_test(nlpql)
    if not success:
        return Response(json.dumps(nlpql_json, indent=4, sort_keys=True), status=400, mimetype='application/json')
    nlpql_json['document_sets'] = list()
    no_docs = False
    docs = ["Docs"]
    if not source_id or len(source_id) == 0 or source_id == 'UNKNOWN':
        util.log("no or invalid source id provided", util.ERROR)
        no_docs = True
    else:
        doc_set = get_document_set(source_id)
        nlpql_json['document_sets'].append(doc_set)

    data_entities = nlpql_json['data_entities']

    filtered_data_entities = list()
    for de in data_entities:
        is_valid_task = True

        if no_docs:
            funct = de.get('funct', '').lower()
            if 'cql' in funct:
                if patient_id and len(str(patient_id)) > 0 and patient_id != -1:
                    is_valid_task = True
                else:
                    is_valid_task = False
            else:
                is_valid_task = False

        if is_valid_task:
            de['named_arguments']['documentset'] = docs
            de['named_arguments']['cql_eval_url'] = util.cql_eval_url
            de['named_arguments']['patient_id'] = patient_id
            de['named_arguments']['encounter_id'] = encounter_id
            de['named_arguments']['source_id'] = source_id
            de['named_arguments']['fhir_data_service_uri'] = fhir_data_service_uri
            de['named_arguments']['fhir_auth_type'] = fhir_auth_type
            de['named_arguments']['fhir_auth_token'] = fhir_auth_token
            de['named_arguments']['fhir_terminology_service_uri'] = util.fhir_terminology_service_uri
            de['named_arguments']['fhir_terminology_service_endpoint'] = util.fhir_terminology_service_endpoint
            de['named_arguments']['fhir_terminology_user_name'] = util.fhir_terminology_user_name
            de['named_arguments']['fhir_terminology_user_password'] = util.fhir_terminology_user_password

            de['named_arguments']['fhir_auth_id_token'] = fhir_auth_id_token
            de['named_arguments']['fhir_auth_patient'] = fhir_auth_patient
            de['named_arguments']['fhir_auth_expires_in'] = fhir_auth_expires_in
            de['named_arguments']['fhir_auth_scope'] = fhir_auth_scope
            de['named_arguments']['fhir_client_id'] = fhir_client_id
            de['named_arguments']['fhir_scope'] = fhir_scope
            de['named_arguments']['fhir_redirect_uri'] = fhir_redirect_uri
            de['named_arguments']['fhir_key'] = fhir_key
            de['named_arguments']['fhir_registration_uri'] = fhir_registration_uri
            de['named_arguments']['fhir_authorize_uri'] = fhir_authorize_uri
            de['named_arguments']['fhir_token_uri'] = fhir_token_uri
            de['named_arguments']['fhir_version'] = fhir_version

            filtered_data_entities.append(de)

    num_data_entities = len(filtered_data_entities)

    if num_data_entities == 0:
        util.log('No valid NLPQL tasks for this query. This subject likely has no documents, and no structured tasks'
                 ' were queried OR this subject has no documents, and also no patient identifier was provided. Try '
                 'passing in "fhir" metadata.', util.ERROR)
        return Response(json.dumps(results, indent=4), status=200, mimetype='application/json')

    print('NAMED ARGUMENTS:')
    print(data_entities[0]['named_arguments'])

    nlpql_json['data_entities'] = filtered_data_entities
    # Submitting the job
    job_success, job_info = submit_job(nlpql_json)
    if not job_success:
        return Response(json.dumps({'message': 'Could not submit job to NLP API. Reason: ' + job_info}, indent=4),
                        status=500,
                        mimetype='application/json')

    if not synchronous:
        job_info['source_id'] = source_id
        job_info['completed'] = False
        return Response(json.dumps(job_info, indent=4),
                        status=200,
                        mimetype='application/json')

    # Getting the results of the Job
    job_id = int(job_info['job_id'])
    log("\n\njob_id = " + str(job_id))
    results, got_results = get_results(job_id, source_data=report_payload, report_ids=report_ids, patient_id=patient_id,
                                       name=nlpql_json.get('name'))

    # Deleting uploaded documents
    delete_obj = delete_report(source_id)
    if not delete_obj[0]:
        return Response(
            json.dumps({'message': 'Could not delete reports from Solr. Reason: ' + delete_obj[1]}, indent=4),
            status=500,
            mimetype='application/json')

    log("\n\nRun Time = %s \n\n" % (time.time() - start), util.INFO)
    return Response(clean_output(results, report_list=report_payload, return_null_results=return_null_results),
                    status=200, mimetype='application/json')


def async_results(job_id, source_id, return_null_results=False):
    """
    Main worker function
    """
    start = time.time()
    report_success, reports = get_reports(source_id)
    if not report_success:
        return Response('''
        {
            "success": false,
            "message": "No matching reports found in Solr.
        }
        ''', status=200, mimetype='application/json')
    report_ids = [x['report_id'] for x in reports]

    job_id = int(job_id)
    log("\n\njob_id = " + str(job_id))
    results, got_results = get_results(job_id, source_data=reports, report_ids=report_ids,
                                       name=str(job_id))

    if got_results:
        # Deleting uploaded documents
        delete_obj = delete_report(source_id)
        if not delete_obj[0]:
            return Response(
                json.dumps({'message': 'Could not delete reports from Solr. Reason: ' + delete_obj[1]}, indent=4),
                status=500,
                mimetype='application/json')

        log("\n\nRun Time = %s \n\n" % (time.time() - start))
        return Response(clean_output(results, report_list=reports, return_null_results=return_null_results), status=200,
                        mimetype='application/json')
    else:
        return Response(results, status=200, mimetype='application/json')


if __name__ == '__main__':
    # y = 'https://www.cdc.gov/about/pdf/facts/cdcfastfacts/cdcfastfacts.pdf'
    # log(get_text(y, base64_encoded=False))
    #
    # h = {
    #     'Accept': 'application/json+fhir'
    # }
    # u = 'https://fhir-open.sandboxcerner.com/dstu2/0b8a0111-e8e6-4c26-a91c-5069cbc6b1ca/Binary/TR-5927259'
    # log(get_text(u, h, key="content"))
    log('nlpaas')