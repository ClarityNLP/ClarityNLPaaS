#!/bin/bash
set -e

echo "Loading NLPQL"
dirname="/api/nlpql/$CUSTOM_DIR"
mkdir $dirname
wget  -P $dirname $CUSTOM_S3_URL
count=`ls -1 *.zip 2>/dev/null | wc -l`
if [ count != 0 ]; then
unzip "$dirname/*.zip" -d $dirname
fi

exec "$@"
