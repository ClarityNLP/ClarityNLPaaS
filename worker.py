import json
import string
import requests
from flask import Response
from random import randint
from pymongo import MongoClient
import time
import util
from bson.json_util import dumps

# Input validation
def validateInput(data):
    if 'reports' not in data:
        return (False, "Input JSON is invalid")

    if len(data['reports']) > 10:
        return (False, "Max 10 reports per request.")

    return (True, "Valid Input")

# Uploading input to Solr
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

# Deleting the uploaded report
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



# Getting the required nlpql from the nlpql directory
def getNLPQL(file_path, sourceId):
    with open(file_path, "r") as file:
        content = file.read()

    updatedContent = content % (sourceId)
    print("\n\nNLPQL:\n")
    print(updatedContent)
    return updatedContent

# Submitting the job to ClarityNLP
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

# TODO
# Checking if the user has an active job
def hasActiveJob(data):
    # TODO: Query Mongo and see if the user has any current active job
    # If active job is present return
    return False

# Reading results from Mongo and converting into JSON
def getResults(data):
    jobId = int(data['job_id'])
    print("\n\nJobID = " + str(jobId))

    # Polling for job completion
    while(True):
        r = requests.get(data['status_endpoint'])

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

# Main function
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
    return Response(results, status=200, mimetype='application/json')
