#!/bin/bash

# Initialize variables
accessToken=""
refreshToken=""

# Parse command line arguments
for arg in "$@"; do
    case $arg in
        --accessToken=*)
        accessToken="${arg#*=}"
        ;;
        --refreshToken=*)
        refreshToken="${arg#*=}"
        ;;
        *)
        # Unknown option
        echo "Unknown option: $arg"
        echo "Usage: $0 --accessToken=<value> --refreshToken=<value>"
        exit 1
        ;;
    esac
done

# Check if both tokens are provided
if [ -z "$accessToken" ] || [ -z "$refreshToken" ]; then
    echo "Error: Both --accessToken and --refreshToken are required"
    echo "Usage: $0 --accessToken=<value> --refreshToken=<value>"
    exit 1
fi

# Create the JSON file
cat > /pythagora/tokens.json << EOF
{
    "accessToken": "$accessToken",
    "refreshToken": "$refreshToken"
}
EOF