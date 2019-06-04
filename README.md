# ClarityNLPaaS

API wrapper around ClarityNLP

## Get all current jobs
- Endpoint: `~/job/list/all`
- Method: `GET`

Returns a JSON list of valid jobs.

## Submitting a job 

- Endpoints: 
    - `~/job/<task>`
    - `~/job/<category>/<task>`
    - `~/job/<group>/<category>/<task>`
- Optional Parameters
    - `async`, e.g. `~/job/<task>?async=true`
        - False by default
        - Returns job metadata, use `source_id` and `job_id` to call the `~/job/results` endpoint to retrieve results.
- Method: `POST`
- Input: JSON
  ```
  {
    "reports": [
      "some report text goes here",
      "another report"
    ]
  }
  ```
  You can also optionally pass in FHIR DocumentReference resources to this endpoint. Additionally,
  you can also pass in the patient_id and a FHIR url if using CQL execution inside of your NLPQL phenotype, e.g.:
  ```
  {
  	"reports": [{
  		"resourceType": "DocumentReference",
  		"id": "1234",
  		"status": "current",
  		"type": {
  			"coding": [{
  				"system": "http://loinc.org",
  				"code": "46208-5",
  				"display": "Nursing notes"
  			}]
  		},
  		"subject": {
  			"reference": "Patient/1927",
  			"display": "GEORGE BURDELL"
  		},
  		"created": "1927-01-01T00:12:00+00:00",
  		"indexed": "2019-03-07T00:12:00.000+00:00",
  		"content": [{
  			"attachment": {
  				"contentType": "text/plain",
  				"language": "en-US",
  				"data": "QmFzZS02NCBlbmNvZGUgeW91ciBkYXRhIGhlcmU="

  			}
  		}]
  	}],
  	"patient_id": "1927",
  	"fhir": {
  		"serviceUrl": "https://apps.hdap.gatech.edu/gt-fhir/fhir",
  		"auth": {
  			"type": "none"
  		}
  	}
  }
  ```
- Return:
    - if *async*: returns a JSON object of job metadata
    - if *not async* (default): returns a JSON array of results



## Getting Job Results
By default, job results return to synchronously to the client. 
However, if the client sets the `async` flag to true on the job request, the client should request the results in this request.
- Endpoint: 
    - `~/job/results`
- Method: `POST`
- Input: JSON
  ```
  {
    "job_id": "1",
    "source_id": "source_abcde",
  }
  ```
- Return:
    - if *completed*: returns a JSON array of results
    - if *not completed*: returns a JSON object with the attribute `completed` set to false



## Adding a new job phenotype

ClarityNLPaaS operated by internally submitting the NLPQL scripts present in the `nlpql` directory. 
In order to add a new job to the service, a new nlpql with a unique file name needs to be added to this directory. 
This new nlpql file name will then serve as the API endpoint. For example, if you add a new nlpql named `test.nlpql`,
 the API endpoint for this job would be `~/job/test`. NLPQL can be nested up to two directories deep as of now.


## Adding a custom job phenotype

These NLPQL scripts don't persist forever (i.e. if the server is refreshed), however they do allow for immediate testing.


- Endpoint: `~/job/register_nlpql`
- Method: `POST`
- Input: TEXT

 ```
phenotype "Karnofksy Score" version "1";

limit 100;

define final KarnofskyScore:
  Clarity.ValueExtraction({
    termset:[KarnofksyTerms],
    minimum_value: "0",
    maximum_value: "100"
    });

```
Your response will tell you the endpoint name that you will use to call this job.
  
  
## Validating NLPQL phenotypes
Use this endpoint to evaluate NLPQL for validity.
- Endpoint: `~/job/validate_nlpql`
- Method: `POST`
- Input: TEXT
 ```
phenotype "Karnofksy Score" version "1";

limit 100;

define final KarnofskyScore:
  Clarity.ValueExtraction({
    termset:[KarnofksyTerms],
    minimum_value: "0",
    maximum_value: "100"
    });

...
```
Your JSON response will have a property `valid`, which will tell you whether the NLPQL is valid or not.
