#!/bin/sh
/usr/local/bin/xray -c config.json &
sleep 3
python test_proxy.py
