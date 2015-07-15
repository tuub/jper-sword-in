#!/bin/sh

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
sudo apt-get update -q -y
sudo apt-get -q -y install libxml2-dev libxslt-dev python-dev lib32z1-dev
cd $DIR/..
. ../../bin/activate
pip install -r requirements.txt

sudo supervisorctl reread jper-sword-in
sudo supervisorctl update jper-sword-in
kill -HUP $(sudo supervisorctl pid jper-sword-in)
