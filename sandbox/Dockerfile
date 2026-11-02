# SEC-17: the image is distroless, without shell, pip or package manager.
# The build stage is the same image plus busybox and uv, so the venvs link
# and the bytecode matches the interpreter that runs them.
FROM gcr.io/distroless/python3-debian13:latest@sha256:0db804f397ca31a1498c9d94c3c1df53fe49ac8007e5942b1cb547c1c3355c09 AS build
COPY --from=gcr.io/distroless/python3-debian13:debug@sha256:b11062384933aff9510c39ce2c46fdb64b87de3414fd73d64e5b669e7c75d961 /busybox /busybox
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /busybox/uv
ENV PATH=/busybox:/usr/bin
SHELL ["/busybox/sh", "-eu", "-c"]
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
# renovate: datasource=github-release-attachments depName=etcd-io/etcd
ARG ETCD_VERSION=v3.7.3
ARG ETCD_SHA256=5dfa9cc3b3ce3b4b491fbcc2057d3daa166bcc6676f743fcd20f8e5760cb9775
ADD --checksum=sha256:${ETCD_SHA256} https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-amd64.tar.gz /tmp/etcd.tgz
# PUB-14a: etcd's archive and the kube-apiserver image ship no licence text,
# so it comes from the release tag. Both are the Apache-2.0 text every release carries.
ADD --checksum=sha256:43ca1b4bbf462789ba15b28373e0c536e510f49e4d05d85a7690cfee94de6f49 https://raw.githubusercontent.com/etcd-io/etcd/${ETCD_VERSION}/LICENSE /tmp/etcd.LICENSE
ADD --checksum=sha256:cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30 https://raw.githubusercontent.com/kubernetes/kubernetes/v1.37.1/LICENSE /tmp/kube-apiserver.LICENSE
COPY requirements.txt /tmp/requirements.txt
COPY krab/requirements.txt /tmp/krab-requirements.txt
# Kapitan's venv is /usr/local, so the interpreter, kapitan and the tools keep
# the paths check.py and policy/binaries.txt name.
RUN mkdir -p /usr/local/bin /home/gate \
 && tar -xzf /tmp/helm.tgz -C /usr/local/bin --strip-components=1 linux-amd64/helm \
 && tar -xzf /tmp/conftest.tgz -C /usr/local/bin conftest \
 && tar -xzf /tmp/etcd.tgz -C /usr/local/bin --strip-components=1 "etcd-${ETCD_VERSION}-linux-amd64/etcd" \
 && tar -xzf /tmp/krab.tgz -C /usr/local/bin --strip-components=1 "krab-${KRAB_VERSION#v}-x86_64-unknown-linux-gnu/krab" \
 && mkdir -p /licenses/helm /licenses/conftest /licenses/krab /licenses/etcd /licenses/kube-apiserver \
 && cp /tmp/etcd.LICENSE /licenses/etcd/LICENSE \
 && cp /tmp/kube-apiserver.LICENSE /licenses/kube-apiserver/LICENSE \
 && tar -xzf /tmp/helm.tgz -C /licenses/helm --strip-components=1 linux-amd64/LICENSE \
 && tar -xzf /tmp/conftest.tgz -C /licenses/conftest LICENSE \
 && tar -xzf /tmp/krab.tgz -C /licenses/krab --strip-components=1 "krab-${KRAB_VERSION#v}-x86_64-unknown-linux-gnu/LICENSE" \
 && chmod -R a+rX /licenses \
 && uv venv -q --allow-existing --python /usr/bin/python3.13 /usr/local \
 && uv pip install -q --no-cache --compile-bytecode --require-hashes --no-deps --python /usr/local/bin/python3.13 -r /tmp/requirements.txt \
 && uv venv -q --python /usr/bin/python3.13 /opt/krab-python \
 && uv pip install -q --no-cache --compile-bytecode --require-hashes --no-deps --python /opt/krab-python/bin/python -r /tmp/krab-requirements.txt \
 && python3.13 -m compileall -q -j0 /usr/lib/python3.13 \
 && echo 'gate:x:10001:10001::/home/gate:/sbin/nologin' >>/etc/passwd \
 && echo 'gate:x:10001:' >>/etc/group \
 && chown 10001:10001 /home/gate

FROM gcr.io/distroless/python3-debian13:latest@sha256:0db804f397ca31a1498c9d94c3c1df53fe49ac8007e5942b1cb547c1c3355c09
COPY --from=build /usr/lib/python3.13 /usr/lib/python3.13
COPY --from=build /usr/local /usr/local
COPY --from=build /opt/krab-python /opt/krab-python
COPY --from=build /etc/passwd /etc/group /etc/
COPY --from=build /home/gate /home/gate
COPY --from=build /licenses /usr/share/doc
COPY --from=registry.k8s.io/kube-apiserver:v1.37.1@sha256:e190f914a6cc21cab9268485d1ae7282fdeab1315ac64b668aa42d732fd1061d /usr/local/bin/kube-apiserver /usr/local/bin/kube-apiserver
# PATH holds only directories that exist, so a program lookup tries no other path (SEC-10).
ENV PATH=/usr/local/bin:/usr/bin \
    KRAB_PYTHON=/opt/krab-python/bin/python KRAB_NO_DAEMON=1 \
    XDG_CACHE_HOME=/tmp/xdg/cache XDG_STATE_HOME=/tmp/xdg/state XDG_RUNTIME_DIR=/tmp/xdg/run \
    GIT_PYTHON_REFRESH=quiet PYTHONDONTWRITEBYTECODE=1 HOME=/home/gate KUBECONFIG=/dev/null HELM_PLUGINS= \
    HELM_CACHE_HOME=/tmp/helm/cache HELM_CONFIG_HOME=/tmp/helm/config HELM_DATA_HOME=/tmp/helm/data
ENTRYPOINT []
USER gate
WORKDIR /project
