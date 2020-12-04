#!/bin/bash

# extra apt installs
apt install pandoc # for pdf exports

# make shared folder
mkdir -p /srv/scratch
chown root:jupyterhub-users /srv/scratch
chmod 777 /srv/scratch
chmod g+s /srv/scratch
ln -s /srv/scratch /etc/skel/scratch
