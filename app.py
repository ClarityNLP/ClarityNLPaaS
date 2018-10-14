from flask import Flask, request, jsonify, Response
from worker import worker

app = Flask(__name__)

@app.route("/")
def hello():
    return "Welcome to ClarityNLPaaS"


"""
API for Value Extraction
"""
@app.route("/valueExtraction", methods=['POST', 'GET'])
def valueExtraction():
    if request.method == "POST":
        data = request.get_json()
        return worker(data)
    else:
        return Response(json.dumps({'message': 'API supports only GET and POST requests'}), status=400, mimetype='application/json')




if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
