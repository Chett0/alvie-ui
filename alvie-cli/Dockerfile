FROM matteobusi/alvie

USER root

WORKDIR /home/alvie/alvie-cli


RUN mkdir -p /var/lib/apt/lists/partial && \
    apt-get update && \
    apt-get install -y python3 python3-pip python-is-python3 python3-venv neovim && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# run alvie-cli as "alvie-cli" from anywhere in the container
RUN echo "alias alvie-cli='python /home/alvie/alvie-cli/alvie-cli'" >> /home/alvie/.bashrc

# Script to load both python venv and bashrc with alvie-cli alias and dune
RUN printf '%s\n' \
  'source /home/alvie/.bashrc' \
  'source /home/alvie/venv/bin/activate' \
  > /home/alvie/.bashrc_alvie

RUN python -m venv /home/alvie/venv

ENV VIRTUAL_ENV="/home/alvie/venv"
ENV ALVIE_CODE_PATH="/home/alvie/alvie/code"
ENV ALVIE_CLI_PATH="/home/alvie/alvie-cli"

RUN pip install --upgrade pip && \
    pip install uv

COPY requirements.txt .

RUN uv pip install -r requirements.txt

COPY --chown=alvie:alvie . .

USER alvie

CMD ["/bin/bash"]