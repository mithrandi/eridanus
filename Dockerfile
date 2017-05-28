FROM pypy:2-5.7.1-slim AS build
RUN apt-get update && DEBIAN_FRONTEND=interactive apt-get install --no-install-recommends -qy gcc libc6-dev libffi-dev libssl-dev ca-certificates libxml2-dev libxslt1-dev libsqlite3-dev libenchant-dev zlib1g-dev libjpeg-dev
RUN pip install --no-cache-dir virtualenv && pypy -m virtualenv /appenv
COPY . /app
RUN /appenv/bin/pip install --no-cache-dir --requirement /app/requirements.txt /app

FROM pypy:2-5.7.1-slim
RUN apt-get update && DEBIAN_FRONTEND=interactive apt-get install --no-install-recommends -qy libffi6 libssl1.0.0 libxml2 libxslt1.1 libsqlite3-0 libenchant1c2a zlib1g libjpeg62-turbo
RUN mkdir /app /db
WORKDIR "/db"
COPY --from=build /appenv /appenv
ENV LC_ALL C.UTF-8
ENV PATH "/appenv/bin:/usr/local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ENTRYPOINT ["/appenv/bin/axiomatic", "-d", "/db/eridanus.axiom"]
CMD ["start", "--nodaemon", "--pidfile", ""]
