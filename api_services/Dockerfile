FROM python:3.7-stretch

WORKDIR /opt/services/

COPY . .

RUN ls && pip install -r requirements.txt
RUN pip install python-socketio --upgrade

CMD [ "python","-u","decider.py" ]