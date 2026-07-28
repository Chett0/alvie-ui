FROM matteobusi/alvie

USER root

WORKDIR /home/alvie/alvie-cli


RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install -y python3 python3-pip python-is-python3 python3-venv neovim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /home/alvie/venv

ENV VIRTUAL_ENV="/home/alvie/venv"
ENV PATH="/home/alvie/venv/bin:/home/alvie/.opam/4.13.1/bin:$PATH"
ENV ALVIE_CODE_PATH="/home/alvie/alvie/code"
ENV WORKING_PATH="/home/alvie/alvie-cli"

RUN pip install --upgrade pip && \
    pip install uv

COPY requirements.txt .

RUN uv pip install -r requirements.txt

COPY --chown=alvie:alvie . .

USER alvie

CMD ["/bin/bash"]