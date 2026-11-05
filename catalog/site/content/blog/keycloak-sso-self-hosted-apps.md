---
title: "Keycloak SSO for Gitea, Open WebUI and Miniflux on Kubernetes"
date: 2026-11-25
topics: [kapitan, keycloak, security, verification]
description: "Keycloak as OIDC provider for Gitea, Open WebUI and Miniflux, with realm, clients and secrets in one Kapitan inventory, tested with scripted logins on kind."
stack:
  recipes: [keycloak, keycloak-operator, postgresql, cert-manager, cnpg, gitea, valkey, open-webui, miniflux]
  generators: [keycloak, certmanager, cloudnative-pg, kubernetes]
  example: sso-keycloak
---

Every self-hosted app comes with its own accounts. Single sign-on moves
them to one identity provider. The app sends the browser there to log in
and gets back a token that names the user. Keycloak is such a provider,
and Gitea, Open WebUI and Miniflux can all use it through OpenID Connect
(OIDC).

Each app that uses Keycloak is a client of it, and each client exists
twice. Keycloak holds a client ID, the redirect URIs it will send a
browser back to, and a client secret. The app holds the same client ID,
the same redirect URI, the same secret and the URL of Keycloak, the
issuer. When one side changes and the other does not, the login breaks.

This post keeps both sides in one [Kapitan](/glossary/#kapitan)
[class](/glossary/#class). The project is
[sso-keycloak](https://github.com/kadet-hub/examples/tree/main/sso-keycloak)
in kadet-hub/examples. Its `check` script deploys Keycloak and the three
apps to a new [kind](/glossary/#kind) cluster on every change and once a
week. It then logs in with curl as a browser would, and fails when a
step below stops working.

## What each recipe brings {#recipes}

All parts come from [recipes](/glossary/#recipe) that kadet-hub
publishes, each in a [target](/glossary/#target) and a namespace of its
own.

- [keycloak](/recipes/keycloak/) 1.0.0 renders one `Keycloak` resource for
  Keycloak 26.8.1 with the [keycloak](/generators/keycloak/) generator
  1.1.0, and its certificate with the
  [certmanager](/generators/certmanager/) generator 1.0.2. It includes
  [postgresql](/recipes/postgresql/) 1.1.0 for the database.
- [keycloak-operator](/recipes/keycloak-operator/) 1.0.0 is the Keycloak
  Operator 26.8.1, which turns that resource into a StatefulSet and
  imports realms. It runs only the Keycloak version it was released with.
- [cert-manager](/recipes/cert-manager/) 1.0.3 and
  [cnpg](/recipes/cnpg/) 1.0.2 are the operators that Keycloak's
  certificate and the PostgreSQL clusters need.
- [gitea](/recipes/gitea/) 1.0.0 runs Gitea 28.3.0 with its own
  postgresql and [valkey](/recipes/valkey/) 1.0.2.
- [open-webui](/recipes/open-webui/) 1.0.0 runs Open WebUI 0.12.5 with
  valkey. Its index record also lists ollama, which this project leaves
  out.
- [miniflux](/recipes/miniflux/) 1.0.0 runs Miniflux 2.3.4 with its own
  PostgreSQL container.

The fetch inventory pins the seven recipes the targets include. `check`
adds the three they include from the signed [index](/glossary/#index),
verifies all ten and the four generators they pin, and pulls them by
[digest](/glossary/#digest), as the
[Open WebUI and SearXNG post](/blog/open-webui-searxng-kubernetes/#verify-then-pull-by-digest)
shows step by step.

## One class for both sides {#class}

`inventory/classes/sso.yml` is included by Keycloak's target and by each
app's target:

```yaml
parameters:
  sso:
    host: sso.example.test
    # The port is part of the issuer. Browsers and pods use this URL alike.
    url: https://${sso.host}:8443
    realm: home
    issuer: ${sso.url}/realms/${sso.realm}
    # The CA that signs Keycloak's certificate, which every app trusts.
    ca: ?{base64:sso/ca.crt}
    clients:
      gitea:
        id: gitea
        url: http://git.example.test
        redirect_uri: ${sso.clients.gitea.url}/user/oauth2/keycloak/callback
        secret: ?{base64:sso/gitea-client-secret||random:str:40}
        group: git
      open-webui:
        id: open-webui
        url: http://chat.example.test
        redirect_uri: ${sso.clients.open-webui.url}/oauth/oidc/callback
        secret: ?{base64:sso/open-webui-client-secret||random:str:40}
        group: chat
      # Miniflux has no group restriction: every user of the realm gets in.
      miniflux:
        id: miniflux
        url: http://rss.example.test
        redirect_uri: ${sso.clients.miniflux.url}/oauth2/oidc/callback
        secret: ?{base64:sso/miniflux-client-secret||random:str:40}
```

The secrets are [refs](/glossary/#ref). The first compile creates each
value and stores it in the refs directory. Keycloak's target and the
app's target name the same ref, so both get the same value. The base64
backend only encodes, so a repository that matters uses one that
encrypts, such as gpg or Vault. The host names end in `.test`, a name
RFC 2606 reserves for testing.

## The realm {#realm}

The target `keycloak` turns the class into a KeycloakRealmImport. An
excerpt of `inventory/targets/keycloak.yml`:

```yaml
generators:
  keycloak:
    instances:
      keycloak:
        hostname:
          hostname: ${sso.url}
    realm_imports:
      home:
        realm:
          realm: ${sso.realm}
          enabled: true
          groups:
            - name: ${sso.clients.gitea.group}
            - name: ${sso.clients.open-webui.group}
            # A group no app admits.
            - name: family
          users:
            - username: alice
              email: alice@example.test
              emailVerified: true
              firstName: Alice
              lastName: Example
              enabled: true
              groups:
                - /${sso.clients.gitea.group}
                - /${sso.clients.open-webui.group}
              credentials:
                - type: password
                  value: ${escape:PASSWORD_ALICE}
            # bob: the same, in the group family only
          clients:
            - clientId: ${sso.clients.gitea.id}
              secret: ${escape:CLIENT_SECRET_GITEA}
              redirectUris:
                - ${sso.clients.gitea.redirect_uri}
              protocolMappers:
                - ${sso.groups_mapper}
            # open-webui the same way, miniflux without the mapper
        spec:
          placeholders:
            PASSWORD_ALICE:
              secret:
                name: sso-users
                key: alice
            CLIENT_SECRET_GITEA:
              secret:
                name: sso-clients
                key: gitea
```

The client ID and the redirect URI are
[interpolations](/glossary/#interpolation) of the class. The secret is a
placeholder. `${escape:CLIENT_SECRET_GITEA}` renders as
`${CLIENT_SECRET_GITEA}`, which the operator's import job replaces with
the key `gitea` of the Secret `sso-clients`. The target renders that
Secret with the [kubernetes](/generators/kubernetes/) generator from the
same refs the apps read:

```yaml
kubernetes:
  secrets:
    sso-clients:
      string_data:
        gitea:
          value: ${sso.clients.gitea.secret}
```

The users' passwords work the same way, from refs with a `random`
function in the Secret `sso-users`. Open WebUI requires an email in the
claims, so every user has one.

`sso.groups_mapper`, defined in the target, adds the claim `groups` with
the user's group names to the ID token and to the userinfo response.
Gitea and Open WebUI read it, so their clients carry the mapper.

The keycloak generator 1.1.0 warns about plaintext credentials for each
user and client, although the values are placeholders.

Keycloak's operator imports a realm only when it does not exist. Its
[realm import guide](https://www.keycloak.org/operator/realm-import) says
the import never updates or deletes a realm. A client changed in the
class after the first import reaches the compiled manifests but not the
running Keycloak. The operator's `KeycloakOIDCClient` resource creates,
updates and deletes a client, as the keycloak generator's README
describes. It is an alpha API of the operator and needs an admin client
for the operator, and this project does not use it.

## The apps {#apps}

Each app's target reads the same entry of the class. Open WebUI takes
everything from variables, `inventory/targets/open-webui.yml`:

```yaml
components:
  open-webui:
    env:
      WEBUI_URL: ${sso.clients.open-webui.url}
      ENABLE_OAUTH_SIGNUP: "True"
      OAUTH_PROVIDER_NAME: Keycloak
      OPENID_PROVIDER_URL: ${sso.issuer}/.well-known/openid-configuration
      OPENID_REDIRECT_URI: ${sso.clients.open-webui.redirect_uri}
      OAUTH_CLIENT_ID: ${sso.clients.open-webui.id}
      OAUTH_CLIENT_SECRET:
        secretKeyRef:
          name: sso-client
          key: secret
      OAUTH_SCOPES: openid email profile
      ENABLE_OAUTH_ROLE_MANAGEMENT: "True"
      OAUTH_ROLES_CLAIM: groups
      OAUTH_ALLOWED_ROLES: ${sso.clients.open-webui.group}
```

With role management on, Open WebUI 0.12.5 turns away a user whose
`groups` claim does not list `chat`. `get_user_role` in `utils/oauth.py`
has three exceptions. The first account Open WebUI creates becomes admin
whatever its groups, and stays admin while it is the only one. A user
without any group gets an account with the role `pending` instead of a
refusal. And once a second account exists, every login sets the role
from the groups again, so the first admin keeps admin only in a group
that `OAUTH_ADMIN_ROLES` lists, `admin` by default. `check` tests the
first exception only, by signing `alice` in first. The other two are
read from the code.

Miniflux reads `OAUTH2_PROVIDER: oidc`, `OAUTH2_OIDC_DISCOVERY_ENDPOINT`
set to the issuer, `OAUTH2_REDIRECT_URL`, `OAUTH2_CLIENT_ID`, the secret
and `OAUTH2_USER_CREATION: 1` the same way. It has no group check.

Gitea keeps its login sources in its database. `app.ini` has no setting
for them, and the admin page or the CLI creates them. The gitea recipe
leaves the chart's OAuth sources out, so the target adds an init
container that runs the CLI after the recipe's `configure-gitea`, which
migrates the database:

```yaml
configure-oauth:
  image: ${components.gitea.image}
  command:
    - bash
    - -ec
    - |
      id=$(gitea admin auth list --vertical-bars | awk -F'|' '$2 ~ /^[[:space:]]*keycloak[[:space:]]*$/ {print $1 + 0}')
      if [ -n "$id" ]; then cmd="update-oauth --id $id"; else cmd=add-oauth; fi
      gitea admin auth $cmd --name keycloak --provider openidConnect \
        --key "$CLIENT_ID" --secret "$CLIENT_SECRET" \
        --auto-discover-url "$ISSUER/.well-known/openid-configuration" \
        --required-claim-name groups --required-claim-value "$GROUP"
```

`ISSUER`, `CLIENT_ID` and `GROUP` come from the class, `CLIENT_SECRET`
from a Secret with the class's ref. The source's name `keycloak` is part
of Gitea's redirect URI, which is why the class spells it out. Gitea
signs a user in only when the `groups` claim lists `git`. Two settings
in `app.ini` let it create the account on the first login, named after
`preferred_username`:

```yaml
GITEA__SERVER__ROOT_URL: ${sso.clients.gitea.url}/
GITEA__OAUTH2_CLIENT__ENABLE_AUTO_REGISTRATION: "true"
GITEA__OAUTH2_CLIENT__USERNAME: preferred_username
```

## Moving an app {#move}

`check` compiles the targets `keycloak` and `gitea` once more, in a copy
of the project where only Gitea's `url` in the class changed to
`http://code.example.test`. The diff of the two compiles:

```text
gitea/manifests/gitea/gitea-deploy.yml
-              value: http://git.example.test/
+              value: http://code.example.test/
keycloak/manifests/keycloak/home-keycloakrealmimport.yml
-          - http://git.example.test/user/oauth2/keycloak/callback
+          - http://code.example.test/user/oauth2/keycloak/callback
```

The first pair is Gitea's `ROOT_URL`, from which Gitea builds the
redirect URI it sends to Keycloak. The second is the redirect URI the
realm import allows for the client `gitea`. Nothing else of the two
targets changes, and `check` fails when it does. Both compiles run
without `--reveal`, so no secret shows in the diff. A running Keycloak
gets the new redirect URI only with a new realm, as the realm section
explains.

## The issuer has to match {#issuer}

An OIDC login runs over two channels. The browser goes to Keycloak's login
form and back to the app. The app then talks to Keycloak over its own
connection: it reads the discovery document, exchanges the browser's code
for tokens and checks the ID token's signature. The issuer, a URL, ties
the two together. The app compares the issuer it was configured with to
the `issuer` field of the discovery document and to the `iss` claim of
the ID token. Scheme, host, port and path all have to be equal.

Keycloak builds every URL it hands out from its `hostname` setting,
`https://sso.example.test:8443` here. A pod that reads the discovery
document through the Service name still gets `sso.example.test` back, for
the token endpoint and the keys as well. So the pods have to reach
Keycloak under the name the browser uses. In a home network that is
split-horizon DNS or a router that sends the public name back inside.
On kind, `check` adds one rule to CoreDNS:

```text
rewrite name exact sso.example.test keycloak-service.keycloak.svc.cluster.local answer auto
```

`answer auto` rewrites the name in the answer back to `sso.example.test`.
The Service `keycloak-service`, which the operator creates, listens on
8443, so the issuer keeps that port.

To see the pitfall, `check` points Miniflux at the in-cluster name, the
value that looks right from inside the cluster:

```text
OAUTH2_OIDC_DISCOVERY_ENDPOINT=https://keycloak-service.keycloak.svc:8443/realms/home
```

On the next login Miniflux reads the discovery document, and go-oidc,
the OIDC library it uses, refuses it. The browser never reaches Keycloak,
and Miniflux logs:

```text
level=ERROR msg="Failed to initialize OIDC provider" error="oidc: failed to initialize provider \"https://keycloak-service.keycloak.svc:8443/realms/home\": oidc: issuer URL provided to client (\"https://keycloak-service.keycloak.svc:8443/realms/home\") did not match the issuer URL returned by provider (\"https://sso.example.test:8443/realms/home\")"
```

Miniflux 2.3.4 reads the discovery document on every login
(`getOAuth2Manager` in `internal/ui/auth.go`), so the error repeats with
each attempt while the rest of Miniflux keeps running.

## TLS with a CA from refs {#tls}

Keycloak serves HTTPS with a certificate from cert-manager. The apps
check that certificate on their channel, so they need the CA that
signed it. Here the CA is two refs. `check` creates it once per run:

```sh
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes -days 2 \
  -subj '/CN=sso-keycloak example CA' -addext basicConstraints=critical,CA:TRUE \
  -addext keyUsage=critical,keyCertSign,cRLSign -keyout ca.key -out ca.crt
kapitan refs --write base64:sso/ca.crt -f ca.crt
kapitan refs --write base64:sso/ca.key -f ca.key
```

`ec_paramgen_curve:prime256v1` is OpenSSL's name for the curve P-256.
A repository runs this once and commits the refs. The target `keycloak`
renders both halves as the Secret `sso-ca` and the
[certmanager](/generators/certmanager/) generator renders the CA Issuer
`sso-ca` that issues Keycloak's certificate. Each app target renders a
Secret `sso-ca` with the certificate only, mounts it at `/etc/sso` and
sets `SSL_CERT_FILE` to `/etc/sso/ca.crt`. With it, all three apps
trust Keycloak's certificate.

Gitea's CLI reads the discovery document when it adds the source, so
the init container needs the variable too. Without it, the first local
run stopped with `x509: certificate signed by unknown authority`.

## Logging in like a browser {#login}

`check` runs curl on the CI runner, with one cookie jar per user. It
reaches Keycloak and the apps through `kubectl port-forward` and curl's
`--connect-to`, which sends a request for `sso.example.test:8443` to the
local end of the port-forward and keeps the URL as it is:

```sh
curl --cacert ca.pem -b "$jar" -c "$jar" -L \
  --connect-to sso.example.test:8443:127.0.0.1:18443 \
  --connect-to git.example.test:80:127.0.0.1:13000 \
  http://git.example.test/user/oauth2/keycloak
```

Here 18443 and 13000 stand for the local ends of the port-forwards to
Keycloak and Gitea. `check` lets kubectl pick free ones.

That URL sends the browser to Keycloak, which answers with its login
form. `check` posts the user name and password to the form's `action`.
Keycloak redirects back to the app's redirect URI with a code, and the
app redirects to its start page once it has the tokens. Without an
`/etc/hosts` entry, the browser side uses the same issuer as the pods.

Each app then names the user of its session. Gitea 28.3.0 accepts only
tokens on its API, so `check` reads the user name from Gitea's settings
page. Open WebUI's `/api/v1/auths/` returns the user. Miniflux's pages
carry `Logged in as <user>`.

## What the CI run showed {#ci}

[Run 42114834453](https://github.com/kadet-hub/examples/actions/runs/42114834453)
of the examples workflow tested commit `587e44b` of
[kadet-hub/examples#156](https://github.com/kadet-hub/examples/pull/156)
on 5 November 2026, on GitHub's `ubuntu-24.04` runner. The durations
below come from the log's timestamps or from what `check` printed, in
whole seconds.

Verifying the index, the ten recipes and the four generators, and
pulling them, took 70 seconds. Creating the CA and the refs, installing
Kapitan with uv and the two compiles took 13 more, for 126 files, and
the compiles of the moved copy 5. kind had the cluster ready 39 seconds
later. The three operators had rolled out 24 seconds after that. Keycloak's
PostgreSQL was ready 30 seconds later, Keycloak after 28 more, and the
realm import done after another 23, 105 seconds after the cluster in
all. The apps took 91 seconds more, image pulls included. Then `check`
printed this within 4 seconds:

```text
issuer https://sso.example.test:8443/realms/home
gitea: alice signed in as alice with her password, ended at http://git.example.test/
open-webui: alice signed in as alice@example.test through Keycloak's session, ended at http://chat.example.test/auth
miniflux: alice signed in as alice through Keycloak's session, ended at http://rss.example.test/unread
open-webui: alice has the role admin
a wrong password: Keycloak answered 'Invalid username or password.' and no app has a session
gitea: bob, not in git, got 'Sign-In Prohibited' and no session
open-webui: bob, not in chat, was sent to /auth with 'You do not have permission to access this resource. Please contact your administrator for assistance.' and no session
miniflux: bob signed in as bob
```

The first line is the `issuer` of the discovery document, read by curl
through the port-forward. It equals the one the pods see. `alice` typed
her password once, on Gitea's login. Open WebUI and Miniflux sent the
browser to Keycloak, which found her session cookie and sent it straight
back with a code. That is the single sign-on. Open WebUI ends on its
page `/auth`, which takes the session token from the cookie it set.
`alice` is admin there, because hers was the first account.

The wrong password ended on Keycloak's form for each of the three apps,
and none of them had a session afterwards. `bob` has a valid password
and a Keycloak session after his first try, so the second and third
app were again a redirect without a form. Gitea and Open WebUI refused
him after reading the `groups` claim, and Miniflux, which reads no
group, let him in.

## What it leaves out {#gaps}

Changes after the first import. The realm import creates the realm once,
as described above.

Logout, token refresh and a second factor. The check signs in only.
Back-channel logout, where Keycloak tells the apps that a session ended,
needs each app to support it and is not set up.

TLS to the apps. The apps serve plain HTTP on their Services, and the
browser reaches them through a port-forward. An ingress or Gateway with
certificates for `git.example.test` and the other names belongs in front
of them, and the redirect URIs in the class then start with `https://`.

High availability. Keycloak and both PostgreSQL clusters run one
instance each, because the cluster has one node.

Open WebUI's `pending` account for a user without a group, and the role
it sets on each login once a second account exists. Both are read from
Open WebUI's code, not tested.
