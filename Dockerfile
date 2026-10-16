FROM ubuntu:24.04

# Without this, some deps try to reconfigure tzdata (default is UTC)
ENV DEBIAN_FRONTEND=noninteractive

# ffmpeg is required for the `encode` (default since v2.0), `ffmpeg`, and `copy` output
# modes; libgl1 and libglib2.0-0 are runtime dependencies of OpenCV.
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Installs the latest release of DVR-Scan from PyPI.
RUN pip3 install --no-cache-dir --break-system-packages dvr-scan

# Mount the folder containing your videos here (`-v "$(pwd):/videos/"`) so that relative
# input/output paths passed to dvr-scan resolve inside the container.
WORKDIR /videos/

ENTRYPOINT ["dvr-scan"]
