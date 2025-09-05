#!/bin/bash

# We want everything to end up here

mkdir /opt/lean

# set $HOME to this

HOME=/opt/lean

cd $HOME

# install elan the lean installer

curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- -y

# add elan to the path

source $HOME/.elan/env

# now install lean4_jupyter

# automatic istallation puts things in the wrong place
# git clone https://github.com/utensil/lean4_jupyter.git && cd lean4_jupyter && ./scripts/prep.sh

# need to do manual installation to use previously installed jupyterhub

lean --version

git clone https://github.com/utensil/lean4_jupyter.git

git clone https://github.com/leanprover-community/repl

cd repl

lake build

ln -s /opt/lean/repl/.lake/build/bin/repl $HOME/.elan/bin/repl

HOME=/root

# make sure we have the previously installed pip in the path
export PATH=/opt/tljh/user/bin:${PATH}

pip install lean4_jupyter

python -m lean4_jupyter.install

# cp -a /usr/local/share/jupyter/kernels/lean4 /opt/tljh/user/share/jupyter/kernels
