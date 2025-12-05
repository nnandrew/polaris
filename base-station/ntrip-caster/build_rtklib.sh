#!/bin/bash

# Exit on error
set -e

# Set build and repo directories
BUILD_DIR="$(pwd)"
REPO_DIR="$BUILD_DIR/RTKLIB"
TARGET_DIR="$REPO_DIR/bin"
SOURCE_DIR="$REPO_DIR/app/consapp"

# Create build directory if it doesn't exist
mkdir -p "$BUILD_DIR"

# Clone RTKLIB repository only if it doesn't exist
if [ ! -d "$REPO_DIR" ]; then
    echo "Cloning RTKLIB repository..."
    git clone https://github.com/rtklibexplorer/RTKLIB.git "$REPO_DIR"
else
    echo "RTKLIB repository already exists. Pulling latest changes..."
    cd "$REPO_DIR"
    git pull
fi

# Build CUI applications
echo "Building RTKLIB CUI applications..."
cd "$SOURCE_DIR/str2str/gcc"
make
cd "$SOURCE_DIR/convbin/gcc"
make
cd "$SOURCE_DIR/rnx2rtkp/gcc"
make

# Copy the built binaries to current application directory
echo "Installing RTKLIB CUI applications..."
mv "$SOURCE_DIR/str2str/gcc/str2str" $TARGET_DIR
mv "$SOURCE_DIR/convbin/gcc/convbin" $TARGET_DIR
mv "$SOURCE_DIR/rnx2rtkp/gcc/rnx2rtkp" $TARGET_DIR

echo "RTKLIB build completed successfully!"
echo "Binaries installed in $TARGET_DIR:"