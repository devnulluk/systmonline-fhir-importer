FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
RUN pip install --no-cache-dir .
RUN useradd --system --uid 10001 importer && mkdir -p /data && chown importer:importer /data
USER importer
VOLUME ["/data"]
ENTRYPOINT ["systmonline-fhir-sync"]
CMD ["--loop"]
