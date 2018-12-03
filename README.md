# ClarityNLPaaS

API wrapper around ClarityNLP

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

ClarityNLPaaS operated by internally submitting the NLPQL scripts present in the `nlpql` directory. In order to add a new job to the service, a new nlpql with a unique file name needs to be added to this directory. One point to note is that the source value _shouldn't_ be hardcoded and should contain the %s access specifier to appropriately inject a unique source ID. This new nlpql file name will then serve as the API endpoint. For example, if you add a new nlpql named `test.nlpql`, the API endpoint for this job would be `~/job/test`.
