FROM postgres:18

ARG PG_TRICKLE_VERSION=0.9.0
ARG PG_TRICKLE_ARCH=linux-amd64

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl tar \
    && curl -fsSL -o /tmp/pg_trickle.tar.gz \
       "https://github.com/grove/pg-trickle/releases/download/v${PG_TRICKLE_VERSION}/pg_trickle-${PG_TRICKLE_VERSION}-pg18-${PG_TRICKLE_ARCH}.tar.gz" \
    && mkdir -p /tmp/pg_trickle \
    && tar -xzf /tmp/pg_trickle.tar.gz -C /tmp/pg_trickle --strip-components=1 \
    && cp /tmp/pg_trickle/lib/*.so "$(pg_config --pkglibdir)/" \
    && cp /tmp/pg_trickle/extension/*.control /tmp/pg_trickle/extension/*.sql "$(pg_config --sharedir)/extension/" \
    && rm -rf /tmp/pg_trickle /tmp/pg_trickle.tar.gz \
   && apt-get purge -y --auto-remove curl \
    && rm -rf /var/lib/apt/lists/*
