FROM python:3.10-bookworm

WORKDIR /app
COPY requirements.txt pyproject.toml src ./

RUN pip install -r requirements.txt

RUN --mount=source=.git,target=./.git,type=bind \
    pip install -e .

ENTRYPOINT ["cc-changelog-gen"]
