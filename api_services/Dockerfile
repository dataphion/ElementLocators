FROM python:3.7-stretch

WORKDIR /opt/services/

COPY . .

RUN ls && pip install -r requirements.txt

CMD [ "python","-u","decider.py" ]