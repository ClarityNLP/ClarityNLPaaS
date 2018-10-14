import json
import string
import requests
from flask import Response

def validateInput(data):
    if 'userId' not in data or 'report' not in data:
        return False

    report = data['report']
    if 'description_attr' not in report or 'report_text' not in report or 'report_type' not in report:
        return False

    return True


def worker(data):
    # Validating the input object
    if validateInput(data) == False:
        return Response(json.dumps({'message': 'Input JSON object is invalid'}), status=400, mimetype='application/json')
    else:
        return Response(json.dumps({'message': 'OK'}), status=200, mimetype='application/json')
