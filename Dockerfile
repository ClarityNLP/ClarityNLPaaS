FROM python:3.10.6

WORKDIR /

COPY requirements.txt requirements.txt
RUN pip3 install -r requirements.txt

EXPOSE 8080

ENV NUM_WORKERS=4

COPY . .

CMD exec gunicorn main:app --workers $NUM_WORKERS --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080