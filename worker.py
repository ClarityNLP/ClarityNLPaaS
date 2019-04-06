import json
import time
import os
from random import randint

import requests
from bson.json_util import dumps
from flask import Response
from pymongo import MongoClient

import util

nlpaas_report_list = list()


def validate_input(data):
    """
    Input request validation
    """
    if 'reports' not in data:
        return False, "Input JSON is invalid"

    # if len(data['reports']) > 10:
    #     return (False, "Max 10 reports per request.")

    return True, "Valid Input"


def upload_report(data):
    """
    Uploading reports with unique source
    """
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'application/json'
    }

    # Generating a source_id
    source_id = randint(100000, 999999)

    payload = list()
    nlpaas_report_list.clear()
    nlpaas_id = 1

    for report in data['reports']:
        json_body = {
            "report_type": "ClarityNLPaaS Document",
            "id": str(source_id) + str(nlpaas_id),
            "report_id": str(source_id) + str(nlpaas_id),
            "source": str(source_id),
            "report_date": "1970-01-01T00:00:00Z",
            "subject": "ClarityNLPaaS Document",
            "report_text": report,
            "nlpaas_id": str(nlpaas_id)
        }
        payload.append(json_body)
        nlpaas_report_list.append(str(source_id) + str(nlpaas_id))
        nlpaas_id += 1

    print("\n\nSource ID = " + str(source_id))
    print("\n\nReport List = " + str(nlpaas_report_list))

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        return True, source_id
    else:
        return False, response.reason


def delete_report(source_id):
    """
    Deleting reports based on generated source
    """
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'text/xml; charset=utf-8',
    }

    data = '<delete><query>source:%s</query></delete>' % source_id

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return True, response.reason
    else:
        return False, response.reason


def get_nlpql(file_path, source_id):
    """
    Getting required NLPQL based on API route
    """
    with open(file_path, "r") as file:
        content = file.read()

    updated_content = content % source_id
    print("\n\nNLPQL:\n")
    print(updated_content)
    return updated_content


def submit_job(nlpql):
    """
    Submitting ClarityNLP job
    """
    url = util.claritynlp_url + "nlpql"
    response = requests.post(url, data=nlpql)
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
    url = util.claritynlp_url + "nlpql_tester"
    response = requests.post(url, data=nlpql)
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
    # TODO: Query Mongo and see if the user has any current active job
    # If active job is present return
    return False


def get_results(data, source_data=None):
    """
    Reading Results from Mongo
    """
    if not source_data:
        source_data = list()

    job_id = int(data['job_id'])
    print("\n\njob_id = " + str(job_id))

    # Checking if it is a dev box
    if util.development_mode == "dev":
        url = data['status_endpoint']
    else:
        status = "status/%s" % job_id
        url = util.claritynlp_url + status
        print(url)

    # Polling for job completion
    while True:
        r = requests.get(url)

        if r.status_code != 200:
            return Response(json.dumps({'message': 'Could not query job status. Reason: ' + r.reason}), status=500,
                            mimetype='application/json')

        if r.json()["status"] == "COMPLETED":
            break

        time.sleep(2.0)

    client = MongoClient(util.mongo_host, util.mongo_port)
    db = client[util.mongo_db]
    collection = db['phenotype_results']
    results = list(collection.find({'job_id': job_id}))
    if len(source_data) > 0:
        for r in results:
            report_id = r['report_id']
            source = r['source']
            doc_index = int(report_id.replace(source, '')) - 1
            source_doc = source_data[doc_index]
            r['report_text'] = source_doc
            print('found source doc')

    result_string = dumps(results)
    return result_string


def get_results_by_job_id(job_id):
    """
    Getting the results of a job by querying the job ID
    """
    status = "status/%s" % job_id

    url = util.claritynlp_url + status
    print(url)
    # if util.development_mode == "dev":
    #     url = util.claritynlp_url + status
    # else:
    #     url = "http://nlp-api/status/%s" %(job_id)

    r = requests.get(url)

    if r.status_code != 200:
        return Response(json.dumps({'message': 'Could not query job status. Reason: ' + r.reason}), status=500,
                        mimetype='application/json')

    if r.json()["status"] != "COMPLETED":
        return Response(json.dumps({'message': 'Job is still in progress'}), status=500, mimetype='application/json')

    client = MongoClient(util.mongo_host, util.mongo_port)
    db = client[util.mongo_db]
    collection = db['phenotype_results']
    cursor = collection.find({'job_id': int(job_id)})

    if cursor.count() == 0:
        return Response(json.dumps({'message': 'No result found'}), status=200, mimetype='application/json')
    else:
        return clean_output(dumps(cursor))


def clean_output(data):
    """
    Function to clean output JSON
    """
    data = json.loads(data)

    # iterate through to check for report_ids that are empty and assign report count from original report_list
    for obj in data:
        nlpaas_array_id = int(str(obj["report_id"])[6:])
        if obj["report_id"] in nlpaas_report_list:
            obj.update({'nlpaas_report_list_id': nlpaas_array_id})
            nlpaas_report_list.remove(obj["report_id"])
    # return null response for reports with no results
    for item in nlpaas_report_list:
        nlpaas_array_id = int(item[6:])
        data += [{'nlpaas_report_list_id': nlpaas_array_id, 'nlpql_feature': 'null'}]

    # keys = ['_id', 'experiencer', 'report_id', 'source', 'phenotype_final', 'temporality', 'subject', 'concept_code',
    #         'report_type', 'inserted_date', 'negation', 'solr_id', 'end', 'start', 'report_date', 'batch', 
    #         'nlpaas_id', 'owner', 'pipeline_id']

    # for k in keys:
    #     for obj in data:
    #         obj.pop(k, None)

    return json.dumps(data)


def worker(job_file_path, data):
    """
    Main worker function
    """
    start = time.time()
    # Checking for active Job
    if has_active_job(data):
        return Response(json.dumps({'message': 'You currently have an active job. Only one active job allowed'}),
                        status=200, mimetype='application/json')

    # Validating the input object
    valid_obj = validate_input(data)
    if not valid_obj[0]:
        return Response(json.dumps({'message': valid_obj[1]}), status=400, mimetype='application/json')

    # Uploading report to Solr
    upload_obj = upload_report(data)
    if not upload_obj[0]:
        return Response(json.dumps({'message': 'Could not upload report. Reason: ' + upload_obj[1]}), status=500,
                        mimetype='application/json')
    else:
        source_id = upload_obj[1]

    # Getting the nlpql from disk
    nlpql = get_nlpql(job_file_path, source_id)

    # Submitting the job
    job_response = submit_job(nlpql)
    if not job_response[0]:
        return Response(json.dumps({'message': 'Could not submit job. Reason: ' + job_response[1]}), status=500,
                        mimetype='application/json')

    # Getting the results of the Job
    results = get_results(job_response[1], source_data=data['reports'])

    # Deleting uploaded documents
    delete_obj = delete_report(source_id)
    if not delete_obj[0]:
        return Response(json.dumps({'message': 'Could not delete report. Reason: ' + delete_obj[1]}), status=500,
                        mimetype='application/json')

    print("\n\nRun Time = %s \n\n" % (time.time() - start))
    return Response(clean_output(results), status=200, mimetype='application/json')
