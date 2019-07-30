#!/bin/bash


if [ -z "$1" ]
then
      exit 0
fi
if [ -z "$2" ]
then
      exit 0
fi
if [ -z "$3" ]
then
      exit 0
fi



dirname="${1}/nlpql/${3}"
mkdir ${dirname}
echo ${dirname}

wget  -P ${dirname} ${2}
count=`ls -1 *.zip 2>/dev/null | wc -l`
if [ count != 0 ]; then
unzip "${dirname}/*.zip" -d ${dirname}
fi
