FROM python:3.13-slim@sha256:bf44cdfcb76cd3b41e879bc058fc37ec5872002ccfde7fcb765e218cde0cd79c
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=v4.3.0
ARG HELM_SHA256=86584a54def73570558f66f5111cc53dfed56689637ae32c1201205d494f54fb
ADD --checksum=sha256:${HELM_SHA256} https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz /tmp/helm.tgz
# renovate: datasource=github-releases depName=open-policy-agent/conftest
ARG CONFTEST_VERSION=0.71.1
ARG CONFTEST_SHA256=c3f6b2a753bd56e377a1e51a95ae3e057f926f2e9139f7d5b5dfbbaf810f7985
ADD --checksum=sha256:${CONFTEST_SHA256} https://github.com/open-policy-agent/conftest/releases/download/v${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION}_Linux_x86_64.tar.gz /tmp/conftest.tgz
# renovate: datasource=github-releases depName=kapicorp/krab
ARG KRAB_VERSION=2.0.0-alpha.5
ARG KRAB_SHA256=c57cb602e6c89174894708e00b9d4373e67f08582fdd6f7b95517a6658ab9c85
ADD --checksum=sha256:${KRAB_SHA256} https://github.com/kapicorp/krab/releases/download/v${KRAB_VERSION}/krab-${KRAB_VERSION}-x86_64-unknown-linux-gnu.tar.gz /tmp/krab.tgz
COPY requirements.txt /tmp/requirements.txt
COPY krab/requirements.txt /tmp/krab-requirements.txt
RUN tar -xzf /tmp/helm.tgz -C /usr/local/bin --strip-components=1 linux-amd64/helm \
 && tar -xzf /tmp/conftest.tgz -C /usr/local/bin conftest \
 && pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
 && tar -xzf /tmp/krab.tgz -C /usr/local/bin --strip-components=1 "krab-${KRAB_VERSION}-x86_64-unknown-linux-gnu/krab" \
 && python -m venv /opt/krab-python \
 && /opt/krab-python/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/krab-requirements.txt \
 && rm /tmp/helm.tgz /tmp/conftest.tgz /tmp/krab.tgz /tmp/requirements.txt /tmp/krab-requirements.txt \
 && useradd -m -u 10001 gate
ENV KRAB_PYTHON=/opt/krab-python/bin/python KRAB_NO_DAEMON=1 \
    XDG_CACHE_HOME=/tmp/xdg/cache XDG_STATE_HOME=/tmp/xdg/state XDG_RUNTIME_DIR=/tmp/xdg/run \
    GIT_PYTHON_REFRESH=quiet PYTHONDONTWRITEBYTECODE=1 HOME=/home/gate KUBECONFIG=/dev/null HELM_PLUGINS= \
    HELM_CACHE_HOME=/tmp/helm/cache HELM_CONFIG_HOME=/tmp/helm/config HELM_DATA_HOME=/tmp/helm/data
USER gate
WORKDIR /project
