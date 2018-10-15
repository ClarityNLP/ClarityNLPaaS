import json
import string
import requests
from flask import Response
import util

# Input validation
def validateInput(data):
    if 'reports' not in data:
        return (False, "Input JSON is invalid")

    if len(data['reports']) > 10:
        return (False, "Max 10 reports per request.")

    return (True, "Valid Input")


def uploadReport(data):
    # Constructing Solr request
    url = util.solr_url + '/update?commit=true'

    headers = {
        'Content-type': 'application/json'
    }

    data = {
        "report_type": data['report']['report_type'],
        "id": data['userId'],
        "report_id": data['userId'],
        "source": data['userId'],
        "report_date": data['report']['report_date'],
        "subject": data['userId'],
        "report_text": data['report']['report_text']
    }

    print(data)


    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        return True
    else:
        return False


def getNLPQL(data):
    # TODO: Write the code to extract the required NLPQL and enter data
    pass

def hasActiveJob(data):
    # TODO: Query Mongo and see if the user has any current active job
    # If active job is present return
    return False


def worker(data):

    # Checking for active Job
    if hasActiveJob(data) == True:
        return Response(json.dumps({'message': 'You currently have an active job. Only one active job allowed'}), status=200, mimetype='application/json')

    # Validating the input object
    validObj = validateInput(data)
    if validObj[0] == False:
        return Response(json.dumps({'message': validObj[1]}), status=400, mimetype='application/json')

    # Uploading report to Solr
    # if uploadReport(data) == False:
    #     return Response(json.dumps({'message': 'Could not upload report to Solr'}), status=500, mimetype='application/json')

    return Response(json.dumps({'message': 'OK'}), status=200, mimetype='application/json')
