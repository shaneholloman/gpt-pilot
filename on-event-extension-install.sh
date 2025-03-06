#!/bin/bash

set -e

# Directory to monitor
MONITOR_DIR="$HOME/.vscode-server/cli/servers"
PATTERN="Stable-*"
EXCLUDE_SUFFIX=".staging"
VSCODE_SERVER_PORT=8080

# Ensure inotify-tools is installed
if ! command -v inotifywait >/dev/null 2>&1; then
  echo "Error: inotifywait is not installed. Please install inotify-tools." >&2
  exit 1
fi

#notes
#home directory is $HOME/.config/Code/User/settings.json

# Create workspace directory and settings
mkdir -p /pythagora/pythagora-core/workspace/.vscode
printf '{\n  "gptPilot.isRemoteWs": true,\n  "gptPilot.useRemoteWs": false,\n  "workbench.colorTheme": "Default Dark+"\n}' > /pythagora/pythagora-core/workspace/.vscode/settings.json

# Start HTTP-based VS Code server
echo "Starting VS Code HTTP server on port $VSCODE_SERVER_PORT..."

# Manual installation of code-server without sudo
if ! command -v code-server >/dev/null 2>&1; then
  echo "Installing code-server directly..."

  # Create directories
  mkdir -p ~/.local/lib/code-server
  mkdir -p ~/.local/bin

  # Download code-server
  VERSION="4.97.2"
  ARCH=$(uname -m)

  if [ "$ARCH" = "x86_64" ]; then
    PLATFORM="amd64"
  elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    PLATFORM="arm64"
  else
    echo "Unsupported architecture: $ARCH"
    exit 1
  fi

  DOWNLOAD_URL="https://github.com/coder/code-server/releases/download/v${VERSION}/code-server-${VERSION}-linux-${PLATFORM}.tar.gz"

  echo "Downloading code-server from $DOWNLOAD_URL"
  curl -L "$DOWNLOAD_URL" -o /tmp/code-server.tar.gz

  # Extract and install
  tar -xzf /tmp/code-server.tar.gz -C ~/.local/lib/code-server --strip-components=1
  ln -s ~/.local/lib/code-server/bin/code-server ~/.local/bin/code-server
  export PATH="$HOME/.local/bin:$PATH"

  # Clean up
  rm /tmp/code-server.tar.gz
fi

# Start code-server and direct to our workspace
echo "Starting code-server..."
~/.local/bin/code-server --auth none --host 0.0.0.0 --port $VSCODE_SERVER_PORT /pythagora/pythagora-core/workspace &
CODE_SERVER_PID=$!
echo $CODE_SERVER_PID > /tmp/vscode-http-server.pid

# Install Pythagora extension in code-server
echo "Installing Pythagora extension..."
~/.local/bin/code-server --install-extension /var/init_data/pythagora-vs-code.vsix

echo "VS Code HTTP server started with PID $CODE_SERVER_PID. Access at http://localhost:$VSCODE_SERVER_PORT"

echo "Monitoring $MONITOR_DIR for new directories matching $PATTERN..."

inotifywait -m -e create -e moved_to --format '%f' "$MONITOR_DIR" | while read -r NEW_ITEM; do
  # Check if the created item matches the pattern
  if [[ "$NEW_ITEM" == $PATTERN && "$NEW_ITEM" != *$EXCLUDE_SUFFIX ]]; then
    echo "Detected new directory: $NEW_ITEM"

    while [ ! -f "$HOME/.vscode-server/cli/servers/$NEW_ITEM/server/bin/code-server" ]; do
      sleep 1
    done

    $HOME/.vscode-server/cli/servers/$NEW_ITEM/server/bin/code-server --install-extension /var/init_data/pythagora-vs-code.vsix
  fi
done
