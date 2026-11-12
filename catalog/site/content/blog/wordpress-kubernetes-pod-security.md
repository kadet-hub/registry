---
title: "WordPress on Kubernetes under Pod Security restricted"
date: 2026-11-29
topics: [kapitan, security, verification]
tools: [WordPress, containerd, Kubernetes]
description: "WordPress on kind as UID 33 bound port 80 only because containerd 2 sets ip_unprivileged_port_start to 0. At 1024, Apache fails with AH00072."
---

The WordPress image bound port 80 as `www-data`, UID 33, on kind without
the sysctl that lets an unprivileged process bind a port below 1024. The
same pod with `net.ipv4.ip_unprivileged_port_start` set to 1024, the
kernel's default, stopped at once:

```text
(13)Permission denied: AH00072: make_sock: could not bind to address [::]:80
(13)Permission denied: AH00072: make_sock: could not bind to address 0.0.0.0:80
no listening sockets available, shutting down
```

The difference is containerd 2, which sets that sysctl to 0 in every pod
unless the pod sets it. The [recipe](/glossary/#recipe)
[wordpress](/recipes/wordpress/) that kadet-hub publishes for
[Kapitan](/glossary/#kapitan) sets it anyway. It is one of three settings
that let the image run under the Pod Security level `restricted`, and this
post goes through all three on [kind](/glossary/#kind). The tests below
ran on 12 November 2026, with kind v0.33.0 and the node image
`kindest/node:v1.37.0`, whose runtime is containerd v2.3.4.

## The recipe

wordpress 1.0.1 runs WordPress 7.1.4 on PHP 8.5 and Apache from the Docker
Official Image `wordpress:7.1.4-php8.5-apache`, as a StatefulSet with its
`wp-content` on a claim. It renders with the
[kubernetes](/generators/kubernetes/) generator 1.14.0 and includes the
recipe [mariadb](/recipes/mariadb/) 1.0.1 for the database. The WordPress
project publishes no chart, so the recipe is designed on the image, and
its proof is a deploy. The image's Apache reported itself as
`Apache/2.4.69 (Debian) PHP/8.5.12`.

## The image starts as root

The image's config sets no user. It starts `docker-entrypoint.sh` with
`apache2-foreground` as root:

```sh
oras manifest fetch-config --platform linux/amd64 docker.io/library/wordpress:7.1.4-php8.5-apache@sha256:41666f6d61dd038f87ceacd6323685bd9818a3a9b3d80d98af3ce9797c403dce | jq -c '.config | {User, Entrypoint, Cmd, WorkingDir, ExposedPorts}'
```

```text
{"User":null,"Entrypoint":["docker-entrypoint.sh"],"Cmd":["apache2-foreground"],"WorkingDir":"/var/www/html","ExposedPorts":{"80/tcp":{}}}
```

As root, the entrypoint hands the files it copies to the user named in
`APACHE_RUN_USER`, `www-data` by default. In a namespace labelled
`pod-security.kubernetes.io/enforce=restricted`, the image's defaults do
not get that far:

```sh
kubectl run wp-default --image=docker.io/library/wordpress:7.1.4-php8.5-apache@sha256:41666f6d61dd038f87ceacd6323685bd9818a3a9b3d80d98af3ce9797c403dce
```

```text
Error from server (Forbidden): pods "wp-default" is forbidden: violates PodSecurity "restricted:latest": allowPrivilegeEscalation != false (container "wp-default" must set securityContext.allowPrivilegeEscalation=false), unrestricted capabilities (container "wp-default" must set securityContext.capabilities.drop=["ALL"]), runAsNonRoot != true (pod or container "wp-default" must set securityContext.runAsNonRoot=true), seccompProfile (pod or container "wp-default" must set securityContext.seccompProfile.type to "RuntimeDefault" or "Localhost")
```

A pod that sets all four is admitted, and the kubelet then refuses to
start it, because the image would still run as root:

```text
container has runAsNonRoot and image will run as root (pod: "wp-nonroot_wordpress(e9c01f2d-e2a2-4fb9-b18d-0d3f480f4b00)", container: wordpress)
```

The pod needs a user ID. The image's `/etc/passwd` has
`www-data:x:33:33:www-data:/var/www:/usr/sbin/nologin`, so the recipe runs
the pod as UID and GID 33.

## Port 80 as UID 33

With `runAsUser: 33` and `runAsGroup: 33` added and no sysctl, WordPress
started on kind:

```text
[Thu Nov 12 18:22:10.122559 2026] [mpm_prefork:notice] [pid 1:tid 1] AH00163: Apache/2.4.69 (Debian) PHP/8.5.12 configured -- resuming normal operations
```

Inside that pod, `id` printed `uid=33(www-data) gid=33(www-data)
groups=33(www-data)`, and `/proc/sys/net/ipv4/ip_unprivileged_port_start`
held 0. The kernel docs define the sysctl per network namespace as the
first unprivileged port. Binding a port below it takes root or
`CAP_NET_BIND_SERVICE`, and the default is 1024
([ip-sysctl](https://docs.kernel.org/networking/ip-sysctl.html)). The
host that ran kind had 1024. The 0 came from the node's containerd:

```sh
docker exec <node> containerd config dump | grep -n -i unprivileged
```

```text
49:    enable_unprivileged_ports = true
50:    enable_unprivileged_icmp = true
```

containerd's CRI docs say that `enable_unprivileged_ports` "configures
net.ipv4.ip_unprivileged_port_start=0 for all containers which are not
using host network and if it is not overwritten by PodSandboxConfig", and
that "before containerd v2.0, this value defaulted to false"
([v2.3.4](https://github.com/containerd/containerd/blob/v2.3.4/docs/cri/config.md),
[v1.7.29](https://github.com/containerd/containerd/blob/v1.7.29/docs/cri/config.md)).
containerd 1.7 with its default config leaves the sysctl alone, and the
pod then has the kernel's default.

This pod reproduces that on kind. It is the same pod with the sysctl set
to 1024 in `spec.securityContext.sysctls`, which overrides containerd's 0:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: wp-port1024
spec:
  securityContext:
    runAsNonRoot: true
    runAsUser: 33
    runAsGroup: 33
    sysctls:
      - name: net.ipv4.ip_unprivileged_port_start
        value: "1024"
    seccompProfile:
      type: RuntimeDefault
  containers:
    - name: wordpress
      image: docker.io/library/wordpress:7.1.4-php8.5-apache@sha256:41666f6d61dd038f87ceacd6323685bd9818a3a9b3d80d98af3ce9797c403dce
      securityContext:
        allowPrivilegeEscalation: false
        capabilities:
          drop: [ALL]
```

Apache exited with code 1 and the three lines at the top of this post,
and the pod went into a restart loop.

The recipe sets the sysctl to 0 in `wordpress.yml`, so the pod does not
depend on the runtime's default:

```yaml
      security_profile: restricted
      # Apache runs as www-data, UID 33 in the image's /etc/passwd, and binds
      # port 80 through the sysctl, which the php image's documentation names.
      workload_security_context:
        runAsUser: 33
        runAsGroup: 33
        fsGroup: 33
        sysctls:
          - name: net.ipv4.ip_unprivileged_port_start
            value: "0"
```

For `security_profile: restricted`, the kubernetes generator adds
`runAsNonRoot: true` and the seccomp profile `RuntimeDefault` to the pod
and `allowPrivilegeEscalation: false` and `drop: [ALL]` to each
container (`_apply_security_profile` in its `base.py`). Pod Security
lists `net.ipv4.ip_unprivileged_port_start` among the sysctls it allows
([Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/)),
and pods that set it were admitted in the `restricted` namespace.

## wp-content on a new claim

Only `wp-content` lives on the claim. At every start, the entrypoint
copies WordPress from `/usr/src/wordpress` into `/var/www/html` with
`tar`, because the core files are not on the claim. As UID 33, `tar`
cannot change the mode of a directory that another user owns.

kind's local-path provisioner creates a hostPath volume whose root is
owned by root with mode 777. The pod's `fsGroup: 33` did not change that,
and mounting the claim's root at `/var/www/html/wp-content` failed:

```text
WordPress not found in /var/www/html - copying now...
tar: ./wp-content: Cannot change mode to rwxrwxrwx: Operation not permitted
tar: Exiting with failure status due to previous errors
```

The container exited with code 2, and 10 minutes later the pod had 6
restarts and was in `CrashLoopBackOff`.

The recipe runs the init container `wp-content` with
`mkdir -p /data/wp-content` on the claim, as UID 33 like the rest of the
pod, and mounts that directory with `subPath: wp-content`. On the claim of
the recipe's own pod, `ls -ldn` on the kind node showed the directory
owned by UID and GID 33:

```text
drwxrwxrwx. 1  0  0 20 Nov 12 18:20 /var/local-path-provisioner/pvc-5f3e4182-c334-44d2-831a-876ef5b52dde_wordpress_data-wordpress-0
drwxr-xr-x. 1 33 33 58 Aug 18 23:42 /var/local-path-provisioner/pvc-5f3e4182-c334-44d2-831a-876ef5b52dde_wordpress_data-wordpress-0/wp-content
```

## The proof

`check wordpress --level deploys` in kadet-hub/recipes compiles the
recipe's `tests/target.yml` with Kapitan 0.36.3, deploys WordPress and
MariaDB on a new kind cluster and runs `tests/smoke`. The script labels
the namespace `enforce=restricted` with `--dry-run=server` and fails on
any warning, which the admission plugin prints for each running pod that
violates the level. It then installs WordPress through its Service, logs
in, publishes a post through the REST API and uploads a PNG. It deletes
`wordpress-0` and reads both again from the new pod. The local run took
222 seconds and reported:

```text
smoke: WordPress 7.1.4 installed through the Service wordpress, published http://wordpress/2026/11/12/smoke/ and served http://wordpress/wp-content/uploads/2026/11/smoke.png, both again after wordpress-0 restarted, with the session of admin. The pods pass Pod Security restricted.
deploys: passed
```

The weekly run of the recipes workflow,
[run 42622189328](https://github.com/kadet-hub/recipes/actions/runs/42622189328),
passed the same check on 9 November 2026 on Kubernetes
[1.37](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378864414),
[1.36](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378863381)
and
[1.35](https://github.com/kadet-hub/recipes/actions/runs/42622189328/job/130378863620),
at the commit `04879f4` that the local run used. A passing deploy does
not show that the sysctl is needed. The pod with 1024 above does.

## What it leaves out

Other runtimes. Only containerd v2.3.4 ran here, with its default and with
the sysctl set by the pod. Adding back the capability `NET_BIND_SERVICE`,
which `restricted` allows, was not tried in place of the sysctl.

Other storage. Only kind's local-path provisioner ran here, so a volume on
which `fsGroup` changes the claim's root was not tested.

The recipe does not install WordPress. The first visitor of
`/wp-admin/install.php` creates the admin account, so install it before
the Service is reachable by others. WordPress connects to MariaDB without
TLS. The recipe can stand in for Bitnami's `wordpress` chart with its
MariaDB, a chart that gets no updates since Bitnami stopped publishing to
Docker Hub
([Bitnami alternatives, chart by chart](/guides/bitnami-chart-alternatives/)).
Moving a release of that chart to the recipe is not tested.
