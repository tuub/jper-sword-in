# JPER SWORD IN

SWORDv2 deposit endpoint for JPER

## Installation

Clone the project:

    git clone https://github.com/JiscPER/jper-sword-in.git

get all the submodules

    cd myapp
    git submodule init
    git submodule update

This will initialise and clone the esprit, magnificent octopus and Simple-Sword-Server libraries

Then get the submodules for Magnificent Octopus

    cd jper-sword-in/magnificent-octopus
    git submodule init
    git submodule update

Create your virtualenv and activate it

    virtualenv /path/to/venv
    source /path/tovenv/bin/activate

Install Esprit, Magnificent Octopus and Simple-Sword-Server (in that order)

To do them all as one, use

    pip install -r requirements.txt

or to do them individually use

    cd myapp/esprit
    pip install -e .
    
    cd myapp/magnificent-octopus
    pip install -e .
    
    cd Simple-Sword-Server
    pip install -e .
    
Create your local config

    cd myapp
    touch local.cfg

Then you can override any config values that you need to

To start the application, you'll also need to install it into the virtualenv just this first time

    cd jper-sword-in
    pip install -e .

Then, start your app with

    python service/web.py

    
