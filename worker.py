import json
import os
import time
import uuid
import base64
import datetime
import dateparser
import tempfile
import PyPDF2
import re

import util
import requests
from bson.json_util import dumps
from flask import Response
import traceback


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
    headers = {
        'Content-type': 'application/json',
        'Authorization': '{} {}'.format(token['token_type'], token['access_token'])
    }
    print(json.dumps(headers, indent=4))
    return headers


def upload_reports(data):
    """
    Uploading reports with unique source
    """
    
    url = util.solr_url + 'update?commit=true'
    print('URL from upload_reports: "{0}"'.format(url))
    
    # Generating a source_id
    rand_uuid = uuid.uuid1()
    source_id = str(rand_uuid)

    payload = list()
    report_list = list()
    nlpaas_id = 1
    fhir_resource = False

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
                if resource_type == 'DiagnosticReport':
                    if 'text' in report:
                        diagnostic_report = report['text']
                        if 'div' in diagnostic_report:
                            clean_txt = re.sub('<[^<]+?>', '', diagnostic_report['div'])
                            txt += clean_txt
                            txt += '\n'
                elif resource_type == 'DocumentReference' and 'content' in report:
                    for c in report['content']:
                        if 'attachment' in c:
                            if 'contentType' in c['attachment']:
                                content_type = c['attachment']['contentType']
                                if content_type == 'application/pdf':
                                    if 'url' in c['attachment']:
                                        url = c['attachment']['url']
                                        response = requests.get(url)
                                        raw_data = response.content

                                        with open(tempfile.NamedTemporaryFile(), 'wb') as temp_file:
                                            temp_file.write(raw_data)

                                        file_name = temp_file.name
                                        pdf_file = open(file_name, 'rb')
                                        pdf_reader = PyPDF2.PdfFileReader(pdf_file)
                                        num_pages = pdf_reader.getNumPages()

                                        for page_num in range(num_pages):
                                            if pdf_reader.isEncrypted:
                                                pdf_reader.decrypt("")
                                                page_text = pdf_reader.getPage(page_num).extractText()
                                                txt += page_text
                                                txt += '\n'
                                            else:
                                                page_text = pdf_reader.getPage(page_num).extractText()
                                                txt += page_text
                                                txt += '\n'
                                        # TODO base64 encoded PDF

                                        os.remove(file_name)
                                elif 'xml' in content_type or 'html' in content_type:
                                    if 'data' in c['attachment']:
                                        clean_txt = re.sub('<[^<]+?>', '', c['attachment']['data'])
                                        txt += clean_txt
                                        txt += '\n'

                            elif 'data' in c['attachment']:
                                decoded_txt = base64.b64decode(c['attachment']['data']).decode("utf-8")
                                txt += decoded_txt
                                txt += '\n'

                json_body["report_text"] = txt
            else:
                json_body["report_text"] = str(report)
        payload.append(json_body)
        report_list.append(report_id)
        nlpaas_id += 1

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=json.dumps(payload, indent=4))
    if response.status_code == 200:
        return True, source_id, report_list, fhir_resource, payload
    else:
        return False, response.reason, report_list, fhir_resource, payload


def delete_report(source_id):
    """
    Deleting reports based on generated source
    """
    url = util.solr_url + 'update?commit=true'
    print('URL from delete_report: "{0}"'.format(url))

    data = '<delete><query>source:%s</query></delete>' % source_id

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=json.dumps(data, indent=4))
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
    response = requests.get(url, headers=get_headers(token))
    if response.status_code == 200:
        res = response.json()['response']
        if not res:
            res = {
                'docs': []
            }
        return True, res['docs']
    else:
        return False, {'reason': response.reason}


def get_nlpql(file_path):
    """
    Getting required NLPQL based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    return content


def submit_job(nlpql_json):
    """
    Submitting ClarityNLP job
    """

    url = util.claritynlp_url + 'phenotype'
    print('URL from submit_job: "{0}"'.format(url))
    
    phenotype_string = json.dumps(nlpql_json)
    print("")
    print(phenotype_string)
    print("")

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=phenotype_string)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                print(data['error'])
                return False, data['error']
        print("\n\nJob Response:\n")
        print(data)
        return True, data
    else:
        print(response.status_code)
        print(response.reason)
        return False, response.reason


def submit_test(nlpql):
    """
    Testing ClarityNLP job
    """

    url = util.claritynlp_url + 'nlpql_tester'
    print('URL from submit_test: "{0}"'.format(url))

    token, oauth = util.app_token()
    response = requests.post(url, headers=get_headers(token), data=nlpql)
    if response.status_code == 200:
        data = response.json()
        if 'success' in data:
            if not data['success']:
                print(data['error'])
                return False, data['error']
        if 'valid' in data:
            if not data['valid']:
                print(data['valid'])
                return False, data['valid']
        print("\n\nJob Response:\n")
        print(data)
        return True, data
    else:
        print(response.status_code)
        print(response.reason)
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
        traceback.print_exc()
        print(ex)

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


def get_results(job_id: int, source_data=None, report_ids=None, return_only_if_complete=False):
    """
    Reading Results from Mongo
    TODO use API endpoing
    """
    if not source_data:
        source_data = list()
    if not report_ids:
        report_ids = list()

    # Checking if it is a dev box
    status = "status/%s" % job_id
    url = util.claritynlp_url + status
    print('URL from get_results: "{0}"'.format(url))    
    
    # Polling for job completion
    while True:
        token, oauth = util.app_token()
        r = oauth.get(url)

        if r.status_code != 200:
            return Response(json.dumps({'message': 'Could not query job status from NLP API. Reason: ' + r.reason}, indent=4),
                            status=500,
                            mimetype='application/json'), False

        try:
            status = r.json()["status"]
        except Exception as ex1:
            traceback.print_exc()
            status = "ERROR"
            break
        if status == "COMPLETED":
            break
        if return_only_if_complete:
            break

        time.sleep(5.0)

    if return_only_if_complete and status != "COMPLETED":
        return '''
            {
                "job_completed": false,
                "job_id":{},
                "status":{}
            }
        '''.format(job_id, status), False

    # /phenotype_paged_results/<int:job_id>/<string:phenotype_final_str>
    """
    Submitting ClarityNLP job
    """
    results = list()
    url = "{}phenotype_paged_results/{}/{}".format(util.claritynlp_url, job_id, 'true')
    url2 = "{}phenotype_paged_results/{}/{}".format(util.claritynlp_url, job_id, 'false')

    response = oauth.get(url)
    response2 = oauth.get(url2)
    final_list = list()
    if response.status_code == 200 and response2.status_code == 200:
        try:

            results.extend(response.json()['results'])
            results.extend(response2.json()['results'])

            for r in results:
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
                if 'cqlexecutiontask' == pipeline_type and 'fhir' == source.lower():
                    # no source docs, data obtained via CQL query
                    r['report_text'] = ''
                    final_list.append(r)
                    continue
                    
                if len(report_ids) > 0 and report_id not in report_ids:
                    continue

                # compute the doc_index encoded in the source field
                doc_index = int(report_id.replace(source, '').replace('_', '')) - 1
                
                if len(source_data) > 0 and doc_index < len(source_data):
                    source_doc = source_data[doc_index]
                    r['report_text'] = source_doc['report_text']
                else:
                    r['report_text'] = r['sentence']
                final_list.append(r)

            result_string = dumps(final_list)
            return result_string, True
        except Exception as ex:
            traceback.print_exc()
            return '''
                "success":"false",
                "message":{}
            '''.format(str(ex)), False

    else:

        return '''
            "success":"false",
            "message":{}
        '''.format(response.reason), False


def clean_output(data, report_list=None):
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


def worker(job_file_path, data, synchronous=True):
    """
    Main worker function
    """
    start = time.time()
    if 'reports' not in data or len(data['reports']) == 0:
        return Response(json.dumps({'message': 'No reports passed into service.'}, indent=4),
                        status=500,
                        mimetype='application/json')

    # Checking for active Job
    if has_active_job(data):
        return Response(
            json.dumps({'message': 'You currently have an active job. Only one active job allowed'}, indent=4),
            status=200, mimetype='application/json')

    # Uploading report to Solr
    status, source_id, report_ids, is_fhir_resource, report_payload = upload_reports(data)
    if not status:
        return Response(json.dumps({'message': 'Could not upload reports to Solr. Reason: ' + source_id}, indent=4),
                        status=500,
                        mimetype='application/json')

    # Getting the nlpql from disk
    nlpql = get_nlpql(job_file_path)

    # Validating the input object
    success, nlpql_json = submit_test(nlpql)
    if not success:
        return Response(json.dumps(nlpql_json, indent=4, sort_keys=True), status=400, mimetype='application/json')
    doc_set = get_document_set(source_id)
    nlpql_json['document_sets'] = list()
    nlpql_json['document_sets'].append(doc_set)

    docs = ["Docs"]
    data_entities = nlpql_json['data_entities']
    fhir_data_service_uri = ''
    fhir_auth_type = ''
    fhir_auth_token = ''
    patient_id = -1
    if 'fhir' in data:
        fhir = data['fhir']
        if 'serviceUrl' in fhir:
            fhir_data_service_uri = fhir['serviceUrl']
        if 'auth' in fhir:
            auth = fhir['auth']
            if 'type' in auth:
                fhir_auth_type = auth['type']
            if 'token' in auth:
                fhir_auth_token = auth['token']
    if 'patient_id' in data:
        patient_id = data['patient_id']
    for de in data_entities:
        de['named_arguments']['documentset']                       = docs
        de['named_arguments']['cql_eval_url']                      = util.cql_eval_url
        de['named_arguments']['patient_id']                        = patient_id
        de['named_arguments']['fhir_data_service_uri']             = fhir_data_service_uri
        de['named_arguments']['fhir_auth_type']                    = fhir_auth_type
        de['named_arguments']['fhir_auth_token']                   = fhir_auth_token
        de['named_arguments']['fhir_terminology_service_uri']      = util.fhir_terminology_service_uri
        de['named_arguments']['fhir_terminology_service_endpoint'] = util.fhir_terminology_service_endpoint
        de['named_arguments']['fhir_terminology_user_name']        = util.fhir_terminology_user_name
        de['named_arguments']['fhir_terminology_user_password']    = util.fhir_terminology_user_password
    nlpql_json['data_entities'] = data_entities

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
    print("\n\njob_id = " + str(job_id))
    results, got_results = get_results(job_id, source_data=report_payload, report_ids=report_ids)

    # Deleting uploaded documents
    delete_obj = delete_report(source_id)
    if not delete_obj[0]:
        return Response(json.dumps({'message': 'Could not delete reports from Solr. Reason: ' + delete_obj[1]}, indent=4),
                        status=500,
                        mimetype='application/json')

    print("\n\nRun Time = %s \n\n" % (time.time() - start))
    return Response(clean_output(results, report_list=report_payload), status=200, mimetype='application/json')


def async_results(job_id, source_id):
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
    print("\n\njob_id = " + str(job_id))
    results, got_results = get_results(job_id, source_data=reports, report_ids=report_ids)

    if got_results:
        # Deleting uploaded documents
        delete_obj = delete_report(source_id)
        if not delete_obj[0]:
            return Response(json.dumps({'message': 'Could not delete reports from Solr. Reason: ' + delete_obj[1]}, indent=4),
                            status=500,
                            mimetype='application/json')

        print("\n\nRun Time = %s \n\n" % (time.time() - start))
        return Response(clean_output(results, report_list=reports), status=200, mimetype='application/json')
    else:
        return Response(results, status=200, mimetype='application/json')

