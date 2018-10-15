import json
import string
import requests
from flask import Response
from random import randint
from pymongo import MongoClient
import util

# Input validation
def validateInput(data):
    if 'reports' not in data:
        return (False, "Input JSON is invalid")

    if len(data['reports']) > 10:
        return (False, "Max 10 reports per request.")

    return (True, "Valid Input")

# Uploading input to Solr
def uploadReport(data):
    # Constructing Solr request
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'application/json'
    }

    # Generating a sourceId
    sourceId = randint(1000, 9999)

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


    print( "Source ID = " + str(sourceId))


    response = requests.post(url, headers=headers, data=json.dumps(payload))
    if response.status_code == 200:
        return (True, sourceId)
    else:
        return (False, response.reason)


# Getting the required nlpql from the nlpql directory
def getNLPQL(file_path, sourceId):
    with open(file_path, "r") as file:
        content = file.read()

    # TODO: Dynamically inject the new source ID
    return content

# Submitting the job to ClarityNLP
def submitJob(nlpql):
    url = util.claritynlp_url + "nlpql"
    response = requests.post(url, data=nlpql)
    if response.status_code == 200:
        data = response.json()
        return (True, data["job_id"])
    else:
        print (response.reason)
        return (False, response.reason)

# TODO
# Checking if the user has an active job
def hasActiveJob(data):
    # TODO: Query Mongo and see if the user has any current active job
    # If active job is present return
    return False

# Reading results from Mongo and converting into JSON
def getResults(jobId):
    client = MongoClient(util.mongo_host, util.mongo_port)
    db = client[util.mongo_db]
    collection = db['phenotype_results']
    cursor = collection.find({'job_id':jobId})

    if cursor.count() == 0:
        return json.dumps({'message':'Job is in progress'})

    results = list()
    for entry in cursor:
        results.append(entry)

    return json.dumps(results)


# Main function
def worker(data):

    # Checking for active Job
    if hasActiveJob(data) == True:
        return Response(json.dumps({'message': 'You currently have an active job. Only one active job allowed'}), status=200, mimetype='application/json')

    # Validating the input object
    validObj = validateInput(data)
    if validObj[0] == False:
        return Response(json.dumps({'message': validObj[1]}), status=400, mimetype='application/json')

    # TODO: Uncomment
    # Uploading report to Solr
    # uploadObj = uploadReport(data)
    # if uploadObj[0] == False:
    #     return Response(json.dumps({'message': 'Could not upload report to Solr. Reason: ' + uploadObj[1]}), status=500, mimetype='application/json')
    # else:
    #     sourceId = uploadObj[1]

    # Getting the nlpql from disk
    nlpql = getNLPQL("nlpql/test.nlpql", sourceId)

    # Submitting the job
    jobResponse = submitJob(nlpql)
    if jobResponse[0] == False:
        return Response(json.dumps({'message': 'Could not submit job. Reason: ' + jobResponse[1]}), status=400, mimetype='application/json')

    jobId = jobResponse[1]
    print("JOB ID = " + str(jobId))


    # Getting the results of the Job
    results = getResults(jobId)
    return Response(results, status=200, mimetype='application/json')
    #return Response(json.dumps({'message': 'OK'}), status=200, mimetype='application/json')
