#!/bin/bash

# from claude

# install code-server and vscode using conda

sudo -E conda install -c conda-forge code-server jupyter-vscode-proxy

# install the lean extension for code-server

mkdir -p /opt/code-server/extensions
/opt/tljh/user/bin/code-server --extensions-dir /opt/code-server/extensions \
     --install-extension leanprover.lean4
chmod -R a+rX /opt/code-server

# adda config file telling user instances where to find the extensions

cat <<EOF > /opt/tljh/config/jupyterhub_config.d/vscode.py
c.Spawner.environment.update({
    "CODE_EXTENSIONSDIR": "/opt/code-server/extensions",
    "ELAN_HOME": "/opt/elan",
})
EOF

# install elan system wide

mkdir -p /opt/elan
curl -sSfL https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
  | sudo env ELAN_HOME=/opt/elan sh -s -- -y --no-modify-path --default-toolchain none
ln -s /opt/elan/bin/* /opt/tljh/user/bin/

# build a shared Mathlib project

export ELAN_HOME=/opt/elan
mkdir -p /opt/lean && cd /opt/lean
lake +leanprover-community/mathlib4:lean-toolchain new course math
cd course
lake exe cache get               # downloads prebuilt Mathlib, ~5 GB; much faster than building
lake build Mathlib ProofWidgets  # should finish quickly if the cache worked
chmod -R a+rX /opt/elan /opt/lean
cd

# turn off restricted mode

cat <<EOF > /etc/skel/.local/share/code-server/User/settings.json
{ "security.workspace.trust.enabled": false }
EOF

# set default toolchain

sudo env ELAN_HOME=/opt/elan elan default $(cat /opt/lean/course/lean-toolchain)

# override git safety settings

for d in /opt/lean/course/.lake/packages/*/; do
  /bin/git config --system --add safe.directory "${d%/}"
done
/bin/git config --system --add safe.directory /opt/lean/course


