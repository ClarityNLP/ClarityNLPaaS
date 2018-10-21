FROM python:3.5.5

MAINTAINER Health Data Analytics

ENV APP_HOME /api
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

COPY requirements.txt $APP_HOME

RUN pip3 install -r requirements.txt

COPY . .

CMD ["python3", "app.py"]
