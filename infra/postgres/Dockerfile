FROM timescale/timescaledb-ha:pg16

USER root

# Install build dependencies for Apache AGE
RUN apt-get update && apt-get install -y build-essential git postgresql-server-dev-16 bison flex

# Clone and compile Apache AGE for PostgreSQL 16
RUN git clone https://github.com/apache/age.git /tmp/age \
    && cd /tmp/age \
    && git checkout PG16 \
    && make USE_PGXS=1 install

# Clean up
RUN apt-get remove -y build-essential git postgresql-server-dev-16 bison flex \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/*

USER postgres
