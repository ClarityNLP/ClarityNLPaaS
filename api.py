import json
import os
import re

from flask import Flask, flash, request, redirect
from flask import Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

import util
from csv_to_form import parse_questions_from_feature_csv as parse_questions
from worker import get_results, worker, submit_test, add_custom_nlpql, get_nlpql, get_file, async_results, \
    upload_reports, delete_report
from subprocess import call

application = Flask(__name__)
CORS(application)


def clean_text(text):
    return (re.sub(r"""
                   [,.;@#?!&$]+  
                   \ *
                   """,
                   "_",
                   text.lower(), flags=re.VERBOSE)).replace(' ', '_')


def allowed_file(filename):
    allowed_extensions = {'csv'}
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def get_files(files, path):
    for (directory_path, directory_names, file_names) in os.walk(path):
        for d in directory_names:
            get_files(files, directory_path + '/' + d)
        for f in file_names:
            if f.endswith('nlpql'):
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


def get_json(files, path):
    for (directory_path, directory_names, file_names) in os.walk(path):
        for d in directory_names:
            get_json(files, directory_path + '/' + d)
        for f in file_names:
            if f.endswith('json'):
                path = (directory_path + '/' + f[0:f.find('.')]).replace('nlpql/', '')
                files.append(path)


def get_nlpql_forms(results=None, with_sorting=True):
    results = list()
    get_json(results, 'nlpql')

    unique = list(set(results))
    if with_sorting:
        return sorted(unique)
    else:
        return unique


def valid_job(job_type):
    return job_type in get_nlpql_options(with_sorting=False)


def get_api_routes():
    return ', '.join(get_nlpql_options())


@application.route("/")
def hello():
    return "Welcome to ClarityNLPaaS."


def get_host(r):
    # print(request.headers)
    if r.is_secure:
        return 'https://{0}/'.format(r.host)
    else:
        return 'http://{0}/'.format(r.host)


@application.route("/report/upload", methods=['POST'])
def upload_report():
    if request.method == 'POST':
        # Checking if the selected job is valid
        data = request.get_json()
        status, source_id, report_ids, is_fhir_resource, report_payload = upload_reports(data)
        if not status:
            return Response(json.dumps({
                'message': 'Could not upload reports to Solr. Reason: ' + source_id,
                'success': 'false'
            }, indent=4),
                status=500,
                mimetype='application/json')
        else:
            return Response(json.dumps({
                'message': 'Success',
                'source_id': source_id,
                'reports': report_ids,
                'success': 'true'
            }, indent=4),
                status=200,
                mimetype='application/json')

    else:

        return Response("Invalid route. Only POST accepted",
                        status=200,
                        mimetype='text/plain')


@application.route("/report/delete/<source_id>", methods=['POST'])
def delete_reports(source_id: str):
    if request.method == 'POST':
        # Checking if the selected job is valid
        delete_obj = delete_report(source_id)
        if not delete_obj[0]:
            return Response(
                json.dumps({
                    'message': 'Could not delete reports from Solr. Reason: ' + delete_obj[1],
                    'success': 'false'
                }, indent=4),
                status=500,
                mimetype='application/json')
        else:
            return Response(json.dumps({
                'success': 'true',
                'message': 'Success',
                'reason': delete_obj[1]
            }, indent=4),
                status=200,
                mimetype='application/json')
    else:

        return Response("Invalid route. Only POST accepted",
                        status=200,
                        mimetype='text/plain')


@application.route("/jobs", methods=['POST'])
def submit_job_with_nlpql(j):
	the_json = request.get_json()
	nlpql = the_json.get('nlpql', '')

	try:
		async_job = request.args.get('async') == 'true'
	except:
		async_job = False

	try:
		return_null_results = request.args.get('return_null_results') == 'true'
	except:
		return_null_results = False
	synchronous = not async_job

	if nlpql == '':
		return Response(json.dumps({'message': 'Invalid body for this endpoint. Please make sure NLPQL is passed in.'},
		                           indent=4, sort_keys=True), status=400,
		                mimetype='application/json')

	return worker('', the_json, synchronous=synchronous, return_null_results=return_null_results, nlpql=nlpql)


@application.route("/job/<job_category>/<job_subcategory>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_subcategory(job_category: str, job_subcategory: str, job_name: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    try:
        async_job = request.args.get('async') == 'true'
    except:
        async_job = False

    try:
        return_null_results = request.args.get('return_null_results') == 'true'
    except:
        return_null_results = False
    synchronous = not async_job
    job_type = "{}/{}/{}".format(job_category, job_subcategory, job_name)
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    if not valid_job(job_type):
        return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                   sort_keys=True), status=400,
                        mimetype='application/json')
    if request.method == 'POST':
        # Checking if the selected job is valid
        data = request.get_json()
        return worker(job_file_path, data, synchronous=synchronous, return_null_results=return_null_results)
    else:

        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/<job_category>/<job_name>", methods=['POST', 'GET'])
def submit_job_with_category(job_category: str, job_name: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    try:
        async_arg = request.args.get('async').lower()
        async_job = async_arg == 'true' or async_arg == 't' or async_arg == '1'
    except:
        async_job = False
    synchronous = not async_job
    job_type = "{}/{}".format(job_category, job_name)
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    if not valid_job(job_type):
        return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                   sort_keys=True), status=400,
                        mimetype='application/json')
    if request.method == 'POST':
        # Checking if the selected job is valid
        data = request.get_json()
        return worker(job_file_path, data, synchronous=synchronous)
    else:

        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/<job_type>", methods=['POST', 'GET'])
def submit_job(job_type: str):
    """
    API for triggering jobs
    """
    h = get_host(request)
    # print(h)

    job_type = job_type.replace('~', '/')
    job_file_path = "./nlpql/" + job_type + ".nlpql"
    valid = valid_job(job_type)
    try:
        async_job = request.args.get('async') == 'true'
    except:
        async_job = False
    try:
        return_null_results = request.args.get('return_null_results') == 'false'
    except:
        return_null_results = False
    synchronous = not async_job

    if request.method == 'POST':
        # Checking if the selected job is valid
        if (job_type == 'validate_nlpql' or job_type == 'nlpql_tester') and request.data:
            _, res = submit_test(request.data)
            return json.dumps(res, indent=4, sort_keys=True)
        elif job_type == 'register_nlpql' and request.data:
            res = request.data.decode("utf-8")
            return json.dumps(add_custom_nlpql(res), indent=4, sort_keys=True)
        elif job_type == 'results' and request.data:
            res = request.get_json()
            return async_results(res['job_id'], res['source_id'], return_null_results=return_null_results)
        else:
            if not valid:
                return Response(
                    json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                               sort_keys=True), status=400,
                    mimetype='application/json')
            data = request.get_json()
            return worker(job_file_path, data, synchronous=synchronous)
    else:
        if not valid:
            return Response(json.dumps({'message': 'Invalid API route. Valid Routes: ' + get_api_routes()}, indent=4,
                                       sort_keys=True), status=400,
                            mimetype='application/json')
        return Response(get_nlpql(job_file_path),
                        status=200,
                        mimetype='text/plain')


@application.route("/job/results/<job_id>", methods=['GET'])
def get_results(job_id):
    """
    API for getting Job results
    """
    if request.method == 'GET':
        return get_results(job_id)
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/update/nlpql", methods=['GET'])
def update_nlpql():
    os.environ['CUSTOM_DIR'] = util.custom_nlpql_folder
    os.environ['CUSTOM_S3_URL'] = util.custom_nlpql_s3_bucket
    call(['sh /api/load_nlpql.sh'])
    return "NLPQL update triggered"


@application.route("/job/list/all", methods=['GET'])
def get_nlpql_list():
    """
    API for getting NLPQL Options
    """
    if request.method == 'GET':
        return Response(json.dumps(get_nlpql_options()), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/forms", methods=['GET'])
def get_question_list():
    """
    API for getting NLPQL questions
    """
    if request.method == 'GET':
        form_display = list()
        forms = get_nlpql_forms()
        for f in forms:
            form_obj = dict()
            form_obj['url'] = f

            keys = f.split('/')
            if len(keys) == 0:
                slug = "unknown"
            elif len(keys) > 1:
                slug = keys[-2]
            else:
                slug = keys[-1]
            form_obj['slug'] = slug

            if len(keys) == 3:
                form_res = get_form_with_subcategory(keys[0], keys[1], keys[2])
            elif len(keys) == 2:
                form_res = get_form_with_category(keys[0], keys[1])
            else:
                form_res = get_form(keys[0])

            try:
                the_form = form_res.get_json()
            except Exception as ex:
                the_form = dict()
                util.log(ex, util.ERROR)

            the_form_name = the_form.get("name", "Unknown")
            form_obj['name'] = the_form_name

            the_form_owner = the_form.get("owner", "Unknown")
            form_obj['owner'] = the_form_owner

            the_form_version = the_form.get("version", "-1")
            form_obj['version'] = the_form_version

            the_form_description = the_form.get('description', '')
            form_obj['description'] = the_form_description

            form_display.append(form_obj)

        return Response(json.dumps(form_display, indent=4), status=200, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'API supports only GET requests'}, indent=4, sort_keys=True), status=400,
                        mimetype='application/json')


@application.route("/form/<form_category>/<form_subcategory>/<form_name>", methods=['POST', 'GET'])
def get_form_with_subcategory(form_category: str, form_subcategory: str, form_name: str):
    file_type = "{}/{}/{}".format(form_category, form_subcategory, form_name)
    file_path = "./nlpql/" + file_type + ".json"
    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


@application.route("/form/<form_category>/<form_name>", methods=['POST', 'GET'])
def get_form_with_category(form_category: str, form_name: str):
    file_type = "{}/{}".format(form_category, form_name)
    file_path = "./nlpql/" + file_type + ".json"
    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


@application.route("/form/<form_type>", methods=['POST', 'GET'])
def get_form(form_type: str):
    form_type = form_type.replace('~', '/')
    file_path = "./nlpql/" + form_type + ".json"

    return Response(get_file(file_path),
                    status=200,
                    mimetype='application/json')


@application.route("/upload/form", methods=['POST', 'GET'])
def upload_form():
    upload_folder = 'nlpql/NLPQL_form_content'

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        form_name = request.form['formname']

        if not form_name or len(form_name) == 0:
            return redirect(request.url)

        if file.filename == '':
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(upload_folder, filename)
            file.save(filepath)

            status = "File parsed successfully. Added to available forms."
            try:
                parse_questions(folder_prefix=clean_text(form_name),
                                form_name=form_name.replace('_', ' '),
                                file_name=filepath,
                                output_dir=upload_folder)
            except Exception as ex:
                status = "Failed to upload, {}".format(repr(ex))
                util.log(ex, util.ERROR)

            response_data = {
                'status': status,
                'available_forms': get_nlpql_forms()
            }
            return Response(json.dumps(response_data, indent=4),
                            status=200,
                            mimetype='application/json')
    else:
        return '''
        <!doctype html>
        <head>
        <title>Upload CSV for NLPQL Form Parsing</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/twitter-bootstrap/4.3.1/css/bootstrap.min.css">
        </head>
        <body>
        
        <div class="container">
        <h1>Upload CSV for NLPQL Form Parsing</h1>
        <br>
        
        <div>
            <a href="https://github.com/ClarityNLP/Utilities/blob/master/custom_query/afib.csv" target="_blank">
                (See sample CSV)
            </a>
        </div>
        <form method=post enctype=multipart/form-data>
          <br>
          <input type=text name="formname" class="form-control" placeholder="Form Name">
          <br>
          <input type=file name=file class="form-control-file">
          <br>
          <input type=submit value=Upload class="btn btn-primary">
        </form>
        </div>
        </body>
        '''


if __name__ == '__main__':
    util.app_token()
    application.run(host='0.0.0.0', port=5000, debug=True)
    util.set_logger(application.logger)
