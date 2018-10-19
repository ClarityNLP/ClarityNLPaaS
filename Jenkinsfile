#!/usr/bin/env groovy
pipeline{
    agent any

    environment {
      GTRI_IMAGE_REGISTRY = credentials('gtri-image-registry')
      GTRI_RANCHER_API_ENDPOINT = credentials('gtri-rancher-api-endpoint')
      GTRI_CLARITY_ENV_ID = credentials('gtri-clarity-env-id')
    }

    stages{
        stage('Deploy'){
            steps{
                script{
                    docker.withRegistry("https://${GTRI_IMAGE_REGISTRY}"){
                        def paasImage = docker.build("clarity-paas:1.0", "-f ./Dockerfile .")
                        paasImage.push('latest')
                    }
                }
            }
        }

        stage('Notify'){
            steps{
                script{
                    rancher confirm: true, credentialId: 'gt-rancher-server', endpoint: "${GTRI_RANCHER_API_ENDPOINT}", environmentId: "${GTRI_CLARITY_ENV_ID}", environments: '', image: "${GTRI_IMAGE_REGISTRY}/clarity-paas:latest", ports: '', service: 'ClarityNLP/paas', timeout: 600
                }
            }
        }
    }
}
