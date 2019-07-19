#!/usr/bin/env bash

read_var() {
    VAR=$(grep $1 $2 | xargs)
    IFS="=" read -ra VAR <<< "$VAR"
    echo ${VAR[1]}
}

CUSTOM_GITHUB_DIRECTORY=$(read_var CUSTOM_GITHUB_DIRECTORY .env)
CUSTOM_GITHUB_SSH_KEY=$(read_var CUSTOM_GITHUB_SSH_KEY .env)
CUSTOM_GITHUB_REPO=$(read_var CUSTOM_GITHUB_REPO .env)


RUN mkdir /root/.ssh/
RUN echo "${CUSTOM_GITHUB_SSH_KEY}" > /root/.ssh/id_rsa

git clone ${CUSTOM_GITHUB_REPO} nlpql/${CUSTOM_GITHUB_DIRECTORY}

RUN rm /root/.ssh/id_rsa
