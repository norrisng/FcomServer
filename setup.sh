#!/usr/bin/env bash

echo '(1/2) Setting up virtualenv...'
python3.6 -m venv ./venv
source ./venv/bin/activate

echo '(2/2) Installing required packages...'
pip3 install wheel
pip3 install -r requirements.txt
pip3 install gunicorn
deactivate

echo 'Setup complete. To enter the virtualenv, type "source ./venv/bin/activate".'