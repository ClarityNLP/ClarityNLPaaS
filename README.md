# ClarityNLPaaS

API wrapper around ClarityNLP

## Get all current jobs
- Endpoint: `~/job/list/all`
- Method: `GET`

Returns a JSON list of valid jobs.

## Submitting a job 

- Endpoint: `~/job/<task>`
- Method: `POST`
- Input: JSON
  ```
  {
    "reports": [
      "report 1", 
      "report 2",
      .
      .
      .
      "report 10"
    ]
  }
  ```
  

Currently only 10 documents can be submitted per request. 




## Adding a new job

ClarityNLPaaS operated by internally submitting the NLPQL scripts present in the `nlpql` directory. 
In order to add a new job to the service, a new nlpql with a unique file name needs to be added to this directory. 
This new nlpql file name will then serve as the API endpoint. For example, if you add a new nlpql named `test.nlpql`,
 the API endpoint for this job would be `~/job/test`. NLPQL can be nested up to two directories deep as of now.


## Adding a custom job

These NLPQL scripts don't persist forever (i.e. if the server is refreshed), however they do allow for immediate testing.


- Endpoint: `~/job/register_nlpql`
- Method: `POST`
- Input: TEXT
 ```
phenotype "Karnofksy Score" version "1";

limit 100;

documentset Docs:
     Clarity.createDocumentSet({
         "query":"source:%s"});


```
Your response will tell you the endpoint name that you will use to call this job.
  
  
## Validating NLPQL
Use this endpoint to evaluate NLPQL for validity.
- Endpoint: `~/job/validate_nlpql`
- Method: `POST`
- Input: TEXT
 ```
phenotype "Karnofksy Score" version "1";

limit 100;

documentset Docs:
     Clarity.createDocumentSet({
         "query":"source:%s"});

...
```
Your JSON response will have a property `valid`, which will tell you whether the NLPQL is valid or not.