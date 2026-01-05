#!/bin/bash
#
# edit this file to add the info below

export SERVER_IP=XXXXXX

export SERVER_PUBLIC_KEY=XXXXXX

export LOCAL_IP=XXXXXX

umask 077

wg genkey > /etc/wireguard/private.key

cat /etc/wireguard/private.key | wg pubkey > /etc/wireguard/public.key

export PRIVATE_KEY=$(cat /etc/wireguard/private.key)

envsubst <wg0.conf > /etc/wireguard/wg0.conf
