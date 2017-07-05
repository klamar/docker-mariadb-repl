FROM mariadb:10.1

RUN set -e -x \
    && apt-get update \
    && apt-get install -y python-minimal python-pip \
    && apt-get clean \
    && pip install \
        "PyMySQL==0.7.11"

COPY . /data/repl

CMD ["/data/repl/start.sh"]
