FROM ubuntu:latest

# Without this, some deps try to reconfigure tzdata (default is UTC)
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y python3 python3-pip libgl1-mesa-glx libglib2.0-0

RUN pip3 install dvr-scan

WORKDIR /video/

ENTRYPOINT ["dvr-scan"]
