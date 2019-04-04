import json
import os

from flask import Flask, request, Response
from flask_cors import CORS

from worker import worker, get_results_by_job_id, submit_test

app = Flask(__name__)
CORS(app)


def get_files(files, path):
    for (directory_path, directory_names, file_names) in os.walk(path):
        for d in directory_names:
            get_files(files, directory_path + '/' + d)
        for f in file_names:
            path = (directory_path + '/' + f[0:f.find('.')]).replace('nlpql/', '')
            files.append(path)
            

def get_nlpql_options(with_sorting=True):
    results = list()
    get_files(results, 'nlpql')

    unique = list(set(results))
    if with_sorting:
        return sorted(unique)
    else:
        return unique


def valid_job(job_type):
    return job_type in get_nlpql_options(with_sorting=False)


def get_api_routes():
    return ', '.join(get_nlpql_options())


@app.route("/")
def hello():
    return "Welcome to ClarityNLPaaS."


@app.route("/job/<job_category>/<job_subcategory>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_subcategory(job_category: str, job_subcategory: str, job_name: str):
    """
    API for triggering jobs
    """
    if request.method == 'POST':
        job_type = "{}/{}/{}".format(job_category, job_subcategory, job_name)
        # Checking if the selected job is valid
        if not valid_job(job_type):
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}), status=400,
                            mimetype='application/json')
        else:
            data = request.get_json()
            job_file_path = "nlpql/" + job_type + ".nlpql"
            return worker(job_file_path, data)
    else:
        return Response(json.dumps({'message': 'API supports only POST requests'}), status=400,
                        mimetype='application/json')


@app.route("/job/<job_category>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_category(job_category: str, job_name: str):
    """
    API for triggering jobs
    """
    if request.method == 'POST':
        job_type = "{}/{}".format(job_category, job_name)
        # Checking if the selected job is valid
        if not valid_job(job_type):
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}), status=400,
                            mimetype='application/json')
        else:
            data = request.get_json()
            job_file_path = "nlpql/" + job_type + ".nlpql"
            return worker(job_file_path, data)
    else:
        return Response(json.dumps({'message': 'API supports only POST requests'}), status=400,
                        mimetype='application/json')


@app.route("/job/<job_type>", methods=['POST', 'GET'])
def submit_job(job_type: str):
    """
    API for triggering jobs
    """
    if request.method == 'POST':
        job_type = job_type.replace('~', '/')
        # Checking if the selected job is valid
        if not valid_job(job_type):
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}), status=400,
                            mimetype='application/json')
        else:
            data = request.get_json()
            job_file_path = "nlpql/" + job_type + ".nlpql"
            return worker(job_file_path, data)
    else:
        return Response(json.dumps({'message': 'API supports only POST requests'}), status=400,
                        mimetype='application/json')


@app.route("/job/results/<job_id>", methods=['GET'])
def get_results(job_id):
    """
    API for getting Job results
    """
    if request.method == 'GET':
        return get_results_by_job_id(job_id)
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}), status=400,
                        mimetype='application/json')


@app.route("/job/list/all", methods=['GET'])
def get_nlpql_list():
    """
    API for getting NLPQL Options
    """
    if request.method == 'GET':
        return Response(json.dumps(get_nlpql_options()), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}), status=400,
                        mimetype='application/json')


@app.route("/job/test/nlpql", methods=["POST"])
def nlpql_tester():
    if request.method == 'POST' and request.data:
        _, res = submit_test(request.data)
        return json.dumps(res, indent=4, sort_keys=True),

    return "Please POST text containing NLPQL."


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
