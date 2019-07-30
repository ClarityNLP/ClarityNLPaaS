FROM python:3.5.5

MAINTAINER Health Data Analytics

RUN  apt-get update -y && \
     apt-get upgrade -y && \
     apt-get dist-upgrade -y && \
     apt-get -y autoremove && \
     apt-get clean
RUN apt-get install -y p7zip \
    p7zip-full \
    unace \
    zip \
    unzip

EXPOSE 5000

ARG CUSTOM_S3_URL
ARG CUSTOM_DIR

ENV APP_HOME /api
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY requirements.txt $APP_HOME

RUN pip3 install -r requirements.txt

COPY . .
RUN sh ./load_nlpql.sh $APP_HOME $CUSTOM_S3_URL $CUSTOM_DIR

CMD ["python3", "app.py"]
