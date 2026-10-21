---
title: "gVisor in CI: sandboxing untrusted code on GitHub Actions"
date: 2026-10-21
topics: [sandbox, ci, gate, security]
description: How kadet-hub runs untrusted contributor code in CI inside a gVisor sandbox on GitHub Actions, what it adds over a plain container and what it misses.
---

If your CI executes code that contributors send you, a plain container is not
a boundary. Run it under gVisor with the network off and a read-only root
filesystem, keep a syscall trace, and treat everything else (timeouts, what
you mount in, your tokens) as separate problems. This is what the
[kadet-hub](/) [gate](/glossary/#gate) does to compile contributor-supplied [Kapitan](/glossary/#kapitan) [generators](/glossary/#generator),
and the pieces transfer to any project that runs plugins, formatters, test
code or build scripts from a pull request.

## The problem

A pull request that adds a generator ships Python that the gate has to run to
see what it produces. The same shape shows up anywhere CI runs contributor
code: a linter plugin, a pytest suite, a Terraform provider, a code
formatter. Once that code runs, in-language guardrails do not hold, because
the attacker writes the code and picks the API.

Three defenses that look like confinement are not. Each of these runs with
host Python 3.13 (pinned through `uv`), `python -I`:

A Python audit hook that blocks `subprocess`:

    blocked: subprocess blocked by audit hook
    via fork_exec

The hook rejects `subprocess.run`, then `_posixsubprocess.fork_exec` spawns
the process directly. `fork_exec` never raises the `subprocess.Popen` audit
event, so the hook does not see it. CPython's own `subprocess` is the only
thing that raises that event.

Blocking DNS, against a raw IP (192.0.2.1 is TEST-NET-1):

    name lookup blocked: DNS blocked
    raw-IP connect reached network, result: TimeoutError timed out

`getaddrinfo` is patched to refuse, and the `connect()` to a literal address
leaves the host anyway. Name resolution was never the exfiltration path.

An rlimit and a private `HOME`:

    HOME = $HOME
    RLIMIT_NOFILE = (1048576, 1048576)
    read /etc/passwd -> root:x:0:0:Super User:/root:/bin/bash

Pointing `HOME` at a scratch directory and capping file descriptors does
nothing to stop a read of a path outside `HOME`. Resource limits bound
resource use, not what the filesystem exposes.

## What gVisor changes

gVisor (`runsc`) is a userspace kernel. The sandboxed process makes syscalls
to gVisor, not to the host kernel, so the host attack surface the process can
reach is small. Two options close the holes above. The runs below use the
same scripts inside `runsc --rootless --network=none run`, in an OCI bundle
whose root filesystem is `python:3.13-slim` exported read-only, with no host
mounts.

With `--network=none` the sandbox has no interfaces. In this rootless
bundle setup the network namespace from `runsc spec` already cuts it off,
so the flag matters most where the namespace is shared:

    name lookup blocked: DNS blocked
    raw-IP connect reached network, result: OSError [Errno 101] Network is unreachable

The raw-IP connect now fails at once rather than reaching the network. For a
compile that needs no network, this is the single highest-value flag.

A read-only minimal rootfs with no host mounts:

    HOME = /root
    RLIMIT_NOFILE = (1024, 1024)
    read /etc/passwd -> root:x:0:0:root:/root:/bin/bash

The read resolves inside the container's own filesystem (note the `root`
GECOS field, where the host showed `Super User`). Host paths are gone: a probe
in the same bundle gets `FileNotFoundError` for the host home and for
host scratch directories, while a file bind-mounted at `/mnt/secret` is still
readable. That last point matters: gVisor confines the filesystem to what you
give it, so anything you mount in is in scope.

This is the kadet-hub `sandbox/run` shape. The container runs
`--network none --read-only --user 10001:10001 --cap-drop ALL
--security-opt no-new-privileges` with `/tmp` and `/out` as `noexec` tmpfs,
the project mounted read-only, and no environment inherited from the runner.

## The one gVisor does not stop, and the trace that does

gVisor is not an audit-hook sandbox. The `fork_exec` bypass runs inside it
unchanged: the process is allowed to start a child. What catches it is the
syscall trace. Run the same script under `runsc --strace
--strace-syscalls=execve,... --debug-log=...` and the spawn is in the log:

    python3 E execve(... /bin/echo, [... "/bin/echo", "via", "fork_exec"], ...)

The execve the audit hook never observed is right there, because gVisor is the
kernel the process talks to and writes the trace outside the sandbox, where
the code being judged cannot disable or forge it, and it follows child
processes. The gate installs the `runsc-trace` runtime and fails a compile
whose trace shows any `execve` other than the interpreter, Kapitan's known
probes and the declared binaries, any outbound `connect`, `sendto` or
`sendmsg` to an `AF_INET` address, a read of a decoy file, and a few other
syscalls. That rule set is SEC-10 in the gate spec. The design reasoning is
in [how kadet-hub works](/guides/how-kadet-hub-works/).

## What gVisor does not cover

gVisor is a kernel boundary, not a policy. Four things stay your job.

CPU and wall-clock exhaustion. A sandboxed process can spin or allocate
forever. gVisor does not time it out; you set a job timeout and a memory
bound. The gate runs each compile under a step timeout and a tmpfs size cap.

Data you mount in. Everything inside the rootfs and every bind mount is
reachable. Mount the contributor's input read-only, mount nothing else, and
never mount a checkout that carries secrets or a writable host path.

Your CI token. gVisor does not hide `GITHUB_TOKEN` or other secrets that the
workflow puts in the environment or in a mounted file. The sandbox run should
inherit no environment from the runner, which is why `sandbox/run` uses an
explicit `--env-file` and the gate passes `KUBECONFIG=/dev/null` and an empty
`HELM_PLUGINS`.

The workflow trigger. Run untrusted pull requests under `pull_request`, never
`pull_request_target`. `pull_request_target` runs with the base repository's
secrets and a writable token, so a sandbox around the code does not help if
the workflow itself hands it the keys. GitHub caps the `permissions` key for
fork pull requests under `pull_request`; set `permissions: {}` anyway and add
back only what a step needs.

## Cost

Measured on one workstation, five runs each, same slim rootfs. A trivial
`python -c pass` takes about 0.02 s native and about 0.12 s under gVisor; a
bare sandbox boot (`runsc do /bin/true`) is about 0.07 s. So gVisor adds
roughly 0.07 to 0.10 s of startup per run plus per-syscall overhead. For a CI
compile that already takes seconds, the sandbox is not the bottleneck.

## gVisor vs a plain Docker container (runc) {#gvisor-vs-docker}

The runs so far are unconfined and under rootless `runsc`. To put gVisor
directly against a plain container, the same three scripts also run under
`docker run` with Docker's default runtime (runc) and under `docker run
--runtime=runsc`, every other option equal, so only the runtime changes.
The script is piped in on stdin and nothing else is mounted. These were
measured on the example repository's CI, one `ubuntu-24.04` runner, in
[run 39571252377](https://github.com/kadet-hub/examples/actions/runs/39571252377).

Swapping runc for runsc changes nothing the three scripts can show. The
`fork_exec` child runs under both, because neither runtime is an audit-hook
sandbox. The raw-IP `connect` reaches the network and times out at
192.0.2.1 under both, because the default Docker network routes out either
way; gVisor blocks it only with `--network=none`, as above. The read of
`/etc/passwd` returns the image's own file under both, because the image,
not the runtime, is the filesystem the process sees.

What differs is the kernel the process talks to:

    runc:  Linux 6.17.0-1022-azure
    runsc: Linux 4.19.0-gvisor

Under runc the sandboxed code's syscalls reach the runner's own kernel, so
a bug in that kernel is reachable from the code being judged. Under runsc
they reach gVisor's userspace kernel, and the host kernel surface the code
can touch is small. That is what a plain container does not give you: the
network and the spawn are bounded by flags and the trace, which you set on
runc too, while the runtime is what moves the host kernel out of reach.

Cost of the swap on the same runner, five runs each: a `python -c pass` in
the container is about 0.20 s under runc and about 0.27 s under runsc, so
runsc adds roughly 0.07 s per run. The absolute figures are higher than the
rootless `runsc ... do` numbers above because each `docker run` starts a
container through the daemon, which dominates both runtimes.

This measures gVisor against Docker's default runtime. It does not answer
"gVisor vs Docker Sandboxes", Docker's hosted sandbox product, or gVisor
against microVM runtimes such as Firecracker or Kata, which would need
microVM measurements this example does not take.

## Decoy credentials

Detection beats hope for the untargeted credential stealer. The gate seeds the
sandbox `HOME` with decoy `~/.aws/credentials`, `~/.kube/config`,
`~/.ssh/id_ed25519` and a `~/.gnupg` key, plus decoy `AWS_SECRET_ACCESS_KEY`,
`GITHUB_TOKEN` and `VAULT_TOKEN` in the environment, each random per run. Two
checks fire: the trace fails the run on any `open` of a decoy file, and the
output is scanned for any decoy value in plain, base64 or hex form. A stealer
that scrapes `HOME` and writes what it found into the generated manifests
trips both. Code written specifically against this gate will avoid the decoys;
the point is the untargeted collector, which is most of them.

## A minimal GitHub Actions job

This installs `runsc` with a pinned release and a SHA-512 check (the digest
and release are what kadet-hub pins), then runs the example rootless. Actions
are pinned by commit SHA, `permissions` is empty, and there are no caches.

    name: sandboxed-compile
    on: pull_request
    permissions: {}
    jobs:
      run:
        runs-on: ubuntu-24.04
        steps:
          - uses: actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1 # v7.0.1
            with:
              persist-credentials: false
          - name: Install gVisor
            env:
              GVISOR_RELEASE: "20261005"
              GVISOR_SHA512: 27fed731b432d6a39d908956623fd273979fda66b3ccf4b9c12413ea417c516e18a9dc3cced403fb28efe495d64dce4251f51cf8c4d9f4a72f9833bd96b6bb35
            run: |
              curl -fsSLo runsc.tar.zstd \
                "https://storage.googleapis.com/gvisor/releases/release/${GVISOR_RELEASE}/x86_64/gvisor.tar.zstd"
              echo "${GVISOR_SHA512}  runsc.tar.zstd" | sha512sum -c -
              # runsc starts its sidecars from gvisor-bin/ next to it: unpack everything
              sudo tar --zstd -xf runsc.tar.zstd -C /usr/local/bin
          - name: Allow unprivileged user namespaces
            # ubuntu-24.04 restricts them with AppArmor; rootless runsc fails
            # with "fork/exec /proc/self/exe: permission denied" otherwise
            run: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
          - name: Run contributor code sandboxed
            run: runsc --rootless --network=none --ignore-cgroups do python3 -I pr-code.py

The example repository runs this setup weekly on `ubuntu-24.04`. Its first
run failed without the `sysctl` step: Ubuntu 24.04 lets AppArmor restrict
unprivileged user namespaces, and rootless `runsc` needs them. The step only
changes the throwaway runner.

The gate itself goes further, running under Docker with the `runsc-trace`
runtime so it can judge the syscall trace, which needs daemon configuration
and root on the runner. The rootless `runsc ... do` form above needs neither
and is enough to get the network and filesystem boundary in a plain job.

The escape scripts and a `run` script that reproduces every output above are
in [the example](https://github.com/kadet-hub/examples/tree/main/gvisor-ci).
For how this fits the rest of the registry, see
[kadet-hub generators as supply-chain artifacts](/blog/kapitan-generators-as-supply-chain-artifacts/).
