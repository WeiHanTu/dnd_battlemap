# Use UCSD DSMLP base image
FROM --platform=linux/amd64 ghcr.io/ucsd-ets/datascience-notebook:stable

LABEL maintainer="UC San Diego ITS/ETS <ets-consult@ucsd.edu>"

# Install system packages
USER root
RUN apt-get update && apt-get install -y \
    htop \
    libgl1-mesa-dev \
    libegl1-mesa-dev \
    libglx-mesa0 \
    libglvnd-dev \
    libopengl0 \
    build-essential \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Switch to jovyan user
USER jovyan

# Install uv
RUN pip install uv

# Copy env.yml and create requirements.txt
COPY --chown=jovyan:users env.yml /home/jovyan/env.yml
RUN python -c "import yaml; f=open('/home/jovyan/env.yml'); data=yaml.safe_load(f); f.close(); f=open('/home/jovyan/requirements.txt', 'w'); [f.write(f'{pkg}\n') for pkg in data['dependencies'][-1]['pip']]"

# Install conda packages
RUN mamba install -y -c conda-forge -c defaults \
    python=3.11.6 \
    pip=25.1 \
    setuptools=78.1.1 \
    wheel=0.45.1 \
    openai=1.77.0 \
    pillow=11.1.0 \
    pydantic=2.10.3 \
    pydantic-core=2.27.1 \
    typing_extensions=4.12.2 \
    tqdm=4.67.1 \
    beautifulsoup4=4.12.3 \
    soupsieve=2.5 \
    httpx=0.28.1 \
    httpcore=1.0.2 \
    h11=0.14.0 \
    anyio=4.7.0 \
    sniffio=1.3.0 \
    annotated-types=0.6.0 \
    jiter=0.6.1 \
    distro=1.9.0 && \
    mamba clean -afy

# Create cache directory and set permissions
USER root
RUN mkdir -p /home/jovyan/.cache/uv && chown -R jovyan:users /home/jovyan/.cache
USER jovyan

# Install pip packages
RUN uv pip install --system -r /home/jovyan/requirements.txt

# Copy project files and set permissions
USER root
COPY --chown=jovyan:users . /home/jovyan/work/
RUN chown -R jovyan:users /home/jovyan/work && \
    chmod -R 755 /home/jovyan/work
USER jovyan

# Set working directory
WORKDIR /home/jovyan/work/

# Install infinigen
RUN cd infinigen && uv pip install --system . && cd ..

# Set PYTHONPATH
ENV PYTHONPATH=/home/jovyan/work 