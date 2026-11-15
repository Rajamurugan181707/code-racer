FROM debian:bookworm-slim

# Compilers and runtimes for the three track languages, plus pkill/unshare for the sandbox.
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 gcc libc6-dev openjdk-17-jdk-headless procps util-linux \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --shell /usr/sbin/nologin runner

WORKDIR /app
COPY server.py .

ENV PORT=10000
EXPOSE 10000
CMD ["python3", "-u", "server.py"]
