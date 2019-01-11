from flask import Flask, request, jsonify, Response
from flask_cors import CORS
from worker import worker, getResultsByJobId
import json
import os

app = Flask(__name__)
CORS(app)


def validJob(jobType):
    validJobs = os.listdir("nlpql")
    return jobType in validJobs

def getApiRoutes():
    existingFiles = os.listdir("nlpql")
    results = list()
    for f in existingFiles:
        results.append('~/' + f[0:f.find('.')])
    return ', '.join(results)

def getNLPQLOptions():
    existingFiles = os.listdir("nlpql")
    results = list()
    for f in existingFiles:
        results.append(f[0:f.find('.')])
    return results

@app.route("/")
def hello():
    return "Welcome to ClarityNLPaaS"


"""
API for triggering jobs
"""
@app.route("/job/<jobType>", methods=['POST', 'GET'])
def submitJob(jobType):
    if request.method == 'POST':
        jobType += ".nlpql"
        # Checking if the selected job is valid
        if not validJob(jobType):
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + getApiRoutes()}), status=400, mimetype='application/json')
        else:
            data = request.get_json()
            jobFilePath = "nlpql/" + jobType
            return worker(jobFilePath, data)
    else:
        return Response(json.dumps({'message': 'API supports only POST requests'}), status=400, mimetype='application/json')

"""
API for getting Job results
"""
@app.route("/job/results/<jobId>", methods=['GET'])
def getResults(jobId):
    if request.method == 'GET':
        return getResultsByJobId(jobId)
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}), status=400, mimetype='application/json')

"""
API for getting NLPQL Options
"""
@app.route("/job/list", methods=['GET'])
def getNLPQLList():
    if request.method == 'GET':
        return Response(json.dumps(getNLPQLOptions()), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}), status=400, mimetype='application/json')



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
