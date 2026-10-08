FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
ARG HELM_VERSION=v4.3.0
ARG HELM_SHA256=86584a54def73570558f66f5111cc53dfed56689637ae32c1201205d494f54fb
ADD --checksum=sha256:${HELM_SHA256} https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz /tmp/helm.tgz
RUN tar -xzf /tmp/helm.tgz -C /usr/local/bin --strip-components=1 linux-amd64/helm \
 && rm /tmp/helm.tgz \
 && pip install --no-cache-dir kapitan==0.36.3 \
 && useradd -m -u 10001 gate
ENV GIT_PYTHON_REFRESH=quiet PYTHONDONTWRITEBYTECODE=1
USER gate
WORKDIR /work
