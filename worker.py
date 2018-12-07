import json
import string
import requests
from flask import Response
from random import randint
from pymongo import MongoClient
import time
import util
from bson.json_util import dumps

"""
Input request validation
"""
def validateInput(data):
    if 'reports' not in data:
        return (False, "Input JSON is invalid")

    # if len(data['reports']) > 10:
    #     return (False, "Max 10 reports per request.")

    return (True, "Valid Input")

"""
Uploading reports with unique source
"""
def uploadReport(data):
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'application/json'
    }

    # Generating a sourceId
    sourceId = randint(100000, 999999)

    payload = list()

    id = 1

    for report in data['reports']:
        jsonBody = {
            "report_type":"ClarityNLPaaS doc",
            "id":str(sourceId) + str(id),
            "report_id":str(sourceId) + str(id),
            "source":str(sourceId),
            "report_date":"1970-01-01T00:00:00Z",
            "subject": "ClarityNLPaaS doc",
            "report_text":report
        }
        payload.append(jsonBody)
        id+=1


    print("\n\nSource ID = " + str(sourceId))

    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        return (True, sourceId)
    else:
        return (False, response.reason)

"""
Deleting reports based on generated source
"""
def deleteReport(sourceId):
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'text/xml; charset=utf-8',
    }

    data = '<delete><query>source:%s</query></delete>' % (sourceId)

    response = requests.post(url, headers=headers, data=data)
    if response.status_code == 200:
        return (True, response.reason)
    else:
        return (False, response.reason)



"""
Getting required NLPQL based on API route
"""
def getNLPQL(file_path, sourceId):
    with open(file_path, "r") as file:
        content = file.read()

    updatedContent = content % (sourceId)
    print("\n\nNLPQL:\n")
    print(updatedContent)
    return updatedContent

"""
Submitting ClarityNLP job
"""
def submitJob(nlpql):
    url = util.claritynlp_url + "nlpql"
    response = requests.post(url, data=nlpql)
    if response.status_code == 200:
        data = response.json()
        print("\n\nJob Response:\n")
        print(data)
        return (True, data)
    else:
        print(response.status_code)
        print (response.reason)
        return (False, response.reason)

"""
TODO:
DoS Protection by allowing user to have only one active job
"""
def hasActiveJob(data):
    # TODO: Query Mongo and see if the user has any current active job
    # If active job is present return
    return False

"""
Reading Results from Mongo
"""
def getResults(data):
    jobId = int(data['job_id'])
    print("\n\nJobID = " + str(jobId))


    # Checking if it is a dev box
    if util.development_mode == "dev":
        url = data['status_endpoint']
    else:
        url = "http://nlp-api/status/%s" %(jobId)
        print("\n\n" + url + "\n\n")

    # Polling for job completion
    while(True):
        r = requests.get(url)

        if r.status_code != 200:
            return Response(json.dumps({'message': 'Could not query job status. Reason: ' + r.reason}), status=500, mimetype='application/json')

        if r.json()["status"] == "COMPLETED":
            break

        time.sleep(0.5)


    client = MongoClient(util.mongo_host, util.mongo_port)
    db = client[util.mongo_db]
    collection = db['phenotype_results']
    cursor = collection.find({'job_id':jobId})

    return dumps(cursor)

"""
Getting the results of a job by querying the job ID
"""
def getResultsByJobId(jobId):
    status = "status/%s" % (jobId)

    if util.development_mode == "dev":
        url = util.claritynlp_url + status
    else:
        url = "http://nlp-api/status/%s" %(jobId)
        print(url)

    r = requests.get(url)

    if r.status_code != 200:
        return Response(json.dumps({'message': 'Could not query job status. Reason: ' + r.reason}), status=500, mimetype='application/json')

    if r.json()["status"] != "COMPLETED":
        return Response(json.dumps({'message': 'Job is still in progress'}), status=500, mimetype='application/json')


    client = MongoClient(util.mongo_host, util.mongo_port)
    db = client[util.mongo_db]
    collection = db['phenotype_results']
    cursor = collection.find({'job_id':int(jobId)})

    if cursor.count() == 0:
        return Response(json.dumps({'message': 'No result found'}), status=200, mimetype='application/json')
    else:
        return cleanOutput(dumps(cursor))
        #return dumps(cursor)


"""
Function to clean output JSON
"""
def cleanOutput(data):
    data = json.loads(data)

    keys = ['_id', 'experiencer', 'report_id', 'source', 'phenotype_final', 'temporality', 'subject', 'concept_code', 'report_type', 'inserted_date', 'negation', 'solr_id', 'end', 'start', 'report_date', 'batch', 'owner', 'pipeline_id']

    # for k in keys:
    #     for obj in data:
    #         obj.pop(k, None)

    return json.dumps(data)




"""
Main worker function
"""
def worker(jobFilePath, data):
    start = time.time()
    # Checking for active Job
    if hasActiveJob(data):
        return Response(json.dumps({'message': 'You currently have an active job. Only one active job allowed'}), status=200, mimetype='application/json')

    # Validating the input object
    validObj = validateInput(data)
    if not validObj[0]:
        return Response(json.dumps({'message': validObj[1]}), status=400, mimetype='application/json')

    # Uploading report to Solr
    uploadObj = uploadReport(data)
    if not uploadObj[0]:
        return Response(json.dumps({'message': 'Could not upload report. Reason: ' + uploadObj[1]}), status=500, mimetype='application/json')
    else:
        sourceId = uploadObj[1]

    # Getting the nlpql from disk
    nlpql = getNLPQL(jobFilePath, sourceId)

    # Submitting the job
    jobResponse = submitJob(nlpql)
    if not jobResponse[0]:
        return Response(json.dumps({'message': 'Could not submit job. Reason: ' + jobResponse[1]}), status=500, mimetype='application/json')

    # Getting the results of the Job
    results = getResults(jobResponse[1])

    # Deleting uploaded documents
    deleteObj = deleteReport(sourceId)
    if not deleteObj[0]:
        return Response(json.dumps({'message': 'Could not delete report. Reason: ' + deleteObj[1]}), status=500, mimetype='application/json')

    print("\n\nRun Time = %s \n\n" %(time.time() - start))
    return Response(cleanOutput(results), status=200, mimetype='application/json')

    #return Response(results, status=200, mimetype='application/json')
