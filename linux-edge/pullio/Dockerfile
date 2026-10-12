# Custom wrapper for the upstream hotio Pullio script; no unofficial image required.
FROM docker:cli
RUN apk add --no-cache bash curl jq coreutils \
    && curl -fsSL https://raw.githubusercontent.com/hotio/pullio/master/pullio.sh -o /usr/local/bin/pullio \
    && chmod 755 /usr/local/bin/pullio \
    && docker compose version
COPY pullio/run-pullio.sh /usr/local/bin/run-pullio
ENTRYPOINT ["/bin/bash", "/usr/local/bin/run-pullio"]
