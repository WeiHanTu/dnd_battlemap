# 1) choose base container
# generally use the most recent tag

# base notebook, contains Jupyter and relevant tools
# See https://github.com/ucsd-ets/datahub-docker-stack/wiki/Stable-Tag
# for a list of the most current containers we maintain
ARG BASE_CONTAINER=ghcr.io/ucsd-ets/datascience-notebook:stable

FROM $BASE_CONTAINER

LABEL maintainer="UC San Diego ITS/ETS <ets-consult@ucsd.edu>"

# 2) change to root to install packages
USER root

# Install system utilities and OpenGL development libraries
RUN apt-get update && apt-get install -y \
    htop \
    libgl1-mesa-dev \
    libegl1-mesa-dev \
    libglx-mesa0 \
    libglvnd-dev \
    libopengl0 \
    # Add any other specific OpenGL/EGL/GLX libraries your project might need
 && rm -rf /var/lib/apt/lists/*

# 3) install packages using notebook user
USER jovyan

# Copy the environment file
COPY --chown=jovyan:users env.yml /home/jovyan/env.yml

# Install Python packages from env.yml into the base environment
# This will install both conda and pip packages listed in the file
RUN mamba env update -n base -f /home/jovyan/env.yml && \
    conda clean -tipy

# Copy the rest of the project files
# Ensure .git and other unwanted files are excluded via .dockerignore if necessary
COPY --chown=jovyan:users . /home/jovyan/work/

# Set the working directory
WORKDIR /home/jovyan/work/

# Example: Install Python packages if needed
# RUN conda install -y scikit-learn
# RUN pip install --no-cache-dir networkx scipy

# If your project Infinigen has its own setup scripts or requirements,
# you might need to add them here. For example:
# COPY . /home/jovyan/work/infinigen
# WORKDIR /home/jovyan/work/infinigen
# RUN conda env update -f environment.yml # or similar for your project
# RUN pip install -r requirements.txt # or similar

# Override command to disable running jupyter notebook at launch
# CMD ["/bin/bash"] 