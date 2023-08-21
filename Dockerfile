FROM python:3.10-slim-bookworm

WORKDIR /app
COPY requirements.txt pyproject.toml src ./

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN --mount=source=.git,target=./.git,type=bind \
    pip install -e .

RUN addgroup clog && adduser --home /app --disabled-password --gecos "" --ingroup clog clog

# Disable safe directory since it impedes the use of the application
RUN printf '[safe]\n    directory = *\n' > /app/.gitconfig && chown clog:clog /app/.gitconfig
USER clog

ENTRYPOINT ["cc-changelog-gen"]
