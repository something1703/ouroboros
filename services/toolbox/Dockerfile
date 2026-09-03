FROM us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest

COPY services/toolbox/tools.yaml /config/tools.yaml

# Base image's own ENTRYPOINT is ["/toolbox"] — supply flags as CMD, don't override it.
CMD ["--config=/config/tools.yaml", "--address=0.0.0.0", "--port=5000"]
