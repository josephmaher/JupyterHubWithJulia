#!/bin/bash
#
# These are the settings, which (may) need adjusting

## Seetings for Linux-server install

# leave this empty if you don't have a domain
export domain=

# this should be set to something irrespective
export hostname=

export fqdn=$hostname.$domain
export timezone="America/New_York"

## HTTPS setup, one of: none, self-cert, existing-cert, letsencrypt
#############
export https_setup=none

# needs a value for option "letsencrypt", otherwise leave empty
export email4letsencrypt=

# Need a values for option "existing-cert,", otherwise leave empty
# Point to existing key & certificate files.
# Note, they will be copied to /opt/tljh/state.
export ssl_key=
export ssl_cert=

## For TLJH
############
export jupyteradmin=admin
export jupyteradmin_user=jupyter-$jupyteradmin
# how long a user's server stays alive without user interaction
export tljh_timeout=3600
# memory limit of each user
export tljh_limits_memory=3G
# CPU-core limit of each user
export tljh_limits_cpu=1
# set path to get python and julia of TLJH
# https://tljh.jupyter.org/en/latest/howto/env/user-environment.html#accessing-user-environment-outside-jupyterhub
export PATH=/opt/tljh/user/bin:${PATH}

## For Julia
############

# version of Julia to install. If set to the empty string, Julia will not be installed.
export julia_version="1.11.2"

# Packages to be installed system-wide, separate entries with ":"
# (IJulia gets installed irrespective)
export julia_packages=
