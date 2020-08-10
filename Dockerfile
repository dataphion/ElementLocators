FROM docgow/matching_servicess_base:1.0.0

RUN pip3 install supervisor
RUN mkdir -p /var/log/supervisor
RUN mkdir -p /opt/images
# RUN ln -s /opt/images p_images

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

WORKDIR /opt/services/
COPY . .

EXPOSE 9502
CMD ["/usr/bin/supervisord" ]