#!/bin/bash

export MONGO_DB_DATA=$PYTHAGORA_DATA_DIR/mongodata
mkdir -p $MONGO_DB_DATA

# Start MongoDB in the background
mongod --dbpath "$MONGO_DB_DATA" --bind_ip_all >> $MONGO_DB_DATA/mongo_logs.txt 2>&1 &

export DB_DIR=$PYTHAGORA_DATA_DIR/database

chown -R devuser: $PYTHAGORA_DATA_DIR
su - devuser -c "mkdir -p $DB_DIR"

set -e

# Start the VS Code extension installer/HTTP server script in the background
su - devuser -c "cd /var/init_data/ && ./on-event-extension-install.sh &"

# Set up git config
su - devuser -c "git config --global user.email 'devuser@pythagora.ai'"
su - devuser -c "git config --global user.name 'pythagora'"

# Keep container running
tail -f /dev/null
