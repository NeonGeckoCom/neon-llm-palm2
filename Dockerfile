FROM python:3.9-slim

LABEL vendor=neon.ai \
    ai.neon.name="neon-llm-palm2"

ENV OVOS_CONFIG_BASE_FOLDER neon
ENV OVOS_CONFIG_FILENAME diana.yaml
ENV XDG_CONFIG_HOME /config
COPY docker_overlay/ /

WORKDIR /app
COPY . /app
RUN pip install /app

CMD [ "neon-llm-palm2" ]