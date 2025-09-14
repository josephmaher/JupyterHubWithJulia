#!/bin/bash

# We want everything to end up here

mkdir /opt/lean

# add a profile file for login shells

tee /etc/profile.d/lean.sh >/dev/null <<'EOF'
# Lean/elan (system-wide)
export ELAN_HOME=/opt/lean
export PATH="$ELAN_HOME/bin:$PATH"
EOF

cd /opt/lean

# install elan the lean installer

ELAN_HOME=/opt/lean bash -lc 'curl https://elan.lean-lang.org/elan-init.sh -sSf | sh -s -- --no-modify-path -y'

# add elan to the path

source /opt/lean/.elan/env

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

#HOME=/root

# cp -a /usr/local/share/jupyter/kernels/lean4 /opt/tljh/user/share/jupyter/kernels


# Make Lean (elan) visible to notebook servers

tee /opt/tljh/config/jupyterhub_config.d/lean.py >/dev/null <<'EOF'
# Expose elan + Lean tools to all user servers
c.Spawner.environment = {
    "ELAN_HOME": "/opt/lean",
    # Prepend elan shims so `lean`, `lake`, and (if present) `repl` are found
    "PATH": "/opt/lean/bin:" + "${PATH}",
}
EOF

#tljh-config reload



# make sure we have the previously installed pip in the path
export PATH=/opt/tljh/user/bin:${PATH}

sudo -E /opt/tljh/user/bin/python3 -m pip install --upgrade lean4_jupyter

sudo -E /opt/tljh/user/bin/python3 -m lean4_jupyter.install --sys-prefix



