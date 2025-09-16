# Rover
A 5G-enabled NTRIP client and RTK GPS.

# Purpose

# Prerequisites

# Setup

## Creating Docker Image

Use this command to build an image for the RB5
```bash
docker build -t <tag> . --platform linux/arm64 
```
Replace the tag with the Docker-Repository/etc.

### Uploading the Image to a Docker Repository
```bash
docker push <tag>
```

# Usage

## Pulling Docker Image from Repository
```bash
docker pull <tag>
```

## Running Image
The privileged tag exposes all the devices ports to docker. 
```bash
docker run --privileged -it <tag>
```

