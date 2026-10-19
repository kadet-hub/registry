FROM python:3.13-slim@sha256:70729b46c69b4f1e97c4822c1af3df53a1476cf5ddc6c087c0c10bc3a5678c2f
# renovate: datasource=github-releases depName=helm/helm
ARG HELM_VERSION=v4.3.1
ARG HELM_SHA256=0403a88ae20913d11b10a2467b50087721fea7581736da6b9d3992f5357fe54b
ADD --checksum=sha256:${HELM_SHA256} https://get.helm.sh/helm-${HELM_VERSION}-linux-amd64.tar.gz /tmp/helm.tgz
# renovate: datasource=github-release-attachments depName=open-policy-agent/conftest
ARG CONFTEST_VERSION=v0.71.1
ARG CONFTEST_SHA256=c3f6b2a753bd56e377a1e51a95ae3e057f926f2e9139f7d5b5dfbbaf810f7985
ADD --checksum=sha256:${CONFTEST_SHA256} https://github.com/open-policy-agent/conftest/releases/download/${CONFTEST_VERSION}/conftest_${CONFTEST_VERSION#v}_Linux_x86_64.tar.gz /tmp/conftest.tgz
# renovate: datasource=github-release-attachments depName=kapicorp/krab
ARG KRAB_VERSION=v2.0.0-alpha.5
ARG KRAB_SHA256=c57cb602e6c89174894708e00b9d4373e67f08582fdd6f7b95517a6658ab9c85
ADD --checksum=sha256:${KRAB_SHA256} https://github.com/kapicorp/krab/releases/download/${KRAB_VERSION}/krab-${KRAB_VERSION#v}-x86_64-unknown-linux-gnu.tar.gz /tmp/krab.tgz
COPY --from=registry.k8s.io/kube-apiserver:v1.37.1@sha256:e190f914a6cc21cab9268485d1ae7282fdeab1315ac64b668aa42d732fd1061d /usr/local/bin/kube-apiserver /usr/local/bin/kube-apiserver
# renovate: datasource=github-release-attachments depName=etcd-io/etcd
ARG ETCD_VERSION=v3.7.2
ARG ETCD_SHA256=3a3679bc51a4ee9d30bccea1da7cd4fe62c6fc1d2ca1255068d2c53bf3026135
ADD --checksum=sha256:${ETCD_SHA256} https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-amd64.tar.gz /tmp/etcd.tgz
COPY requirements.txt /tmp/requirements.txt
COPY krab/requirements.txt /tmp/krab-requirements.txt
RUN tar -xzf /tmp/helm.tgz -C /usr/local/bin --strip-components=1 linux-amd64/helm \
 && tar -xzf /tmp/conftest.tgz -C /usr/local/bin conftest \
 && tar -xzf /tmp/etcd.tgz -C /usr/local/bin --strip-components=1 "etcd-${ETCD_VERSION}-linux-amd64/etcd" \
 && pip install --no-cache-dir --require-hashes --no-deps -r /tmp/requirements.txt \
 && tar -xzf /tmp/krab.tgz -C /usr/local/bin --strip-components=1 "krab-${KRAB_VERSION#v}-x86_64-unknown-linux-gnu/krab" \
 && python -m venv /opt/krab-python \
 && /opt/krab-python/bin/pip install --no-cache-dir --require-hashes --no-deps -r /tmp/krab-requirements.txt \
 && rm /tmp/helm.tgz /tmp/conftest.tgz /tmp/etcd.tgz /tmp/krab.tgz /tmp/requirements.txt /tmp/krab-requirements.txt \
 && useradd -m -u 10001 gate
ENV KRAB_PYTHON=/opt/krab-python/bin/python KRAB_NO_DAEMON=1 \
    XDG_CACHE_HOME=/tmp/xdg/cache XDG_STATE_HOME=/tmp/xdg/state XDG_RUNTIME_DIR=/tmp/xdg/run \
    GIT_PYTHON_REFRESH=quiet PYTHONDONTWRITEBYTECODE=1 HOME=/home/gate KUBECONFIG=/dev/null HELM_PLUGINS= \
    HELM_CACHE_HOME=/tmp/helm/cache HELM_CONFIG_HOME=/tmp/helm/config HELM_DATA_HOME=/tmp/helm/data
USER gate
WORKDIR /project
