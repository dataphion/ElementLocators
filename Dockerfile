FROM dataphion/easelqa-matching-service-base:1.0.0

#RUN mkdir srv/api
WORKDIR /srv/api
COPY . .

RUN pip3 install --no-cache-dir -r requirements.txt
RUN pip3 install supervisor
RUN mkdir -p /var/log/supervisor
RUN mkdir -p /opt/images

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/services/
COPY . .

EXPOSE 9502
CMD ["/usr/bin/supervisord" ]
