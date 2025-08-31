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

git clone https://github.com/utensil/lean4_jupyter.git && cd lean4_jupyter && ./scripts/prep.sh


