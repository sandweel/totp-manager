# Kubernetes deployment (kind + Argo CD)

Layout (everything infra-related lives under `infra/`):

```
.sops.yaml                 sops+age encryption rule (age recipient, which files)
infra/
  aws/                     Terraform (EC2, IAM, network, ...) — legacy AWS deploy
  kubernetes/              this folder
    base/                  Kustomize base
      postgres-cluster.yaml  Zalando `postgresql` CR (2 instances + db + user)
      migrate-job.yaml       alembic upgrade head
      deployment.yaml        app Deployment + Service
      ingress.yaml            classic Ingress (class "traefik")
      configmap.yaml
    overlays/kind/          namespace, image tag :dev, secret.yaml (SopsSecret, sops-encrypted)
    kind-cluster.yaml       optional dedicated kind cluster config
  argocd/
    postgres-operator.yaml  Zalando operator as a Helm Application
    application.yaml        totp-manager Application -> kubernetes/overlays/kind
```

## Postgres via the Zalando operator

`base/postgres-cluster.yaml` is a `postgresql` custom resource, not a StatefulSet.
The operator turns it into a Spilo StatefulSet with streaming replication +
Patroni failover, and creates:

| object | purpose |
|--------|---------|
| StatefulSet `totp-psql`, pods `totp-psql-0/-1` | 2 instances (1 master + 1 replica) |
| Service `totp-psql` | current master — this is `DB_HOST` |
| Service `totp-psql-repl` | replicas only |
| Secret `totp.totp-psql.credentials.postgresql.acid.zalan.do` | generated role password (keys `username`, `password`) |
| database `totp` owned by role `totp` | |

The app Deployment and the migrate Job read `DB_PASSWORD` from that generated
Secret via `secretKeyRef`; everything else (`DB_HOST/PORT/NAME/USER`) is in the
ConfigMap. `totp-secret` only carries `ENCRYPTION_KEY` / `SECRET_KEY` / Mailgun.

## Secrets: sops+age via sops-secrets-operator

`overlays/kind/secret.yaml` is not a plain `Secret` — it's a `SopsSecret` CR
(`isindir.github.com/v1alpha3`), encrypted with [sops](https://github.com/getsops/sops)
against an age key, safe to commit to a public repo. The
[sops-secrets-operator](https://github.com/isindir/sops-secrets-operator) (its
own namespace, its own age-key mount — **not** `argocd-repo-server`) watches
`SopsSecret` objects, decrypts them, and creates/owns the real `totp-secret`
Secret from the result. Argo CD/kustomize only ever see ciphertext.

Bootstrap (once per cluster, all out of band — never in git):

```sh
age-keygen -o ~/.config/sops/age/keys-totp-own.txt   # note the printed public key (age1...)

kubectl create namespace sops-secrets-operator
kubectl -n sops-secrets-operator create secret generic sops-age \
  --from-file=key.txt=~/.config/sops/age/keys-totp-own.txt

helm repo add sops https://isindir.github.io/sops-secrets-operator/
helm install sops-secrets-operator sops/sops-secrets-operator \
  -n sops-secrets-operator --version 0.28.1 \
  --set secretsAsFiles[0].name=sops-age \
  --set secretsAsFiles[0].mountPath=/etc/sops-age \
  --set secretsAsFiles[0].secretName=sops-age \
  --set extraEnv[0].name=SOPS_AGE_KEY_FILE \
  --set extraEnv[0].value=/etc/sops-age/key.txt
```

Put the printed **public** key into `.sops.yaml` at the repo root, then encrypt:

```sh
sops --encrypt --in-place infra/kubernetes/overlays/kind/secret.yaml
```

`kubectl -n totp-manager get sopssecret` shows `Healthy` once the operator has
decrypted it and created the owned `totp-secret` Secret. If a plain `Secret`
with that name already existed beforehand (not owned by the operator),
reconciliation fails with `Child secret is not owned by controller` — delete
the stale `Secret` (not the `SopsSecret` CR) and re-apply, or set
`spec.enforceOwnership: true` on the `SopsSecret` to let it take over
automatically. The operator only watches *its own* child Secrets, so a stale
Secret's deletion alone doesn't trigger a re-reconcile — deleting/re-applying
the `SopsSecret` CR does.

Sync order for regular resources (`argocd.argoproj.io/sync-wave`):

| wave | resources |
|------|-----------|
| -2   | Namespace |
| -1   | ConfigMap, `totp-secret` (`SopsSecret`), `postgresql` CR |
| 2    | app Deployment + Service, Ingress |

`totp-migrate` is not a wave at all — it's a **`PreSync` hook**
(`argocd.argoproj.io/hook: PreSync`, `hook-delete-policy: BeforeHookCreation`).
Hooks run before *any* regular resource on every sync that changes something,
and Argo CD deletes/recreates the hook Job itself — no `ttlSecondsAfterFinished`
needed. (Earlier this was a wave-1 resource with a TTL; combined with
`selfHeal: true` that made Kubernetes' own Job GC and Argo CD's drift-healing
fight each other, recreating the Job forever. A hook isn't part of the
continuously-reconciled desired state, so that loop can't happen.)

Both the Job and the Deployment have a `wait-for-postgres` initContainer for
safety, but **the hook annotations only mean something to Argo CD** — a plain
`kubectl apply -k` treats `totp-migrate` as an ordinary Job: it runs once, and
on a later apply with a changed image tag you must `kubectl delete job
totp-migrate` yourself first (immutable `spec.template`, no `Replace=true`
without Argo CD). See 4a below.

---

## 1. Cluster + image

Current kube-context is the `cka` cluster (`cka-*` nodes).

```sh
docker build -t totp-manager:dev .
kind load docker-image totp-manager:dev --name cka
```

`overlays/kind` pins the tag to `dev` with `imagePullPolicy: IfNotPresent`.

## 2. Install the postgres-operator (once per cluster)

Via Helm:

```sh
helm repo add postgres-operator-charts https://opensource.zalando.com/postgres-operator/charts/postgres-operator
helm install postgres-operator postgres-operator-charts/postgres-operator \
  --version 1.14.0 -n postgres-operator --create-namespace \
  --set configKubernetes.enable_pod_antiaffinity=false
kubectl -n postgres-operator rollout status deploy/postgres-operator
```

…or via Argo CD (`infra/argocd/postgres-operator.yaml`), which does the same
with pinned values. Either way this installs the `acid.zalan.do/postgresql`
CRD that `base/postgres-cluster.yaml` needs.

## 3. Install Traefik (once per cluster)

Classic Ingress, controller = Traefik. The official chart creates the
`IngressClass "traefik"` used by `base/ingress.yaml` automatically:

```sh
helm repo add traefik https://traefik.github.io/charts
helm install traefik traefik/traefik -n traefik --create-namespace \
  --set service.spec.type=NodePort
kubectl -n traefik rollout status deploy/traefik
```

`service.spec.type=NodePort` avoids the `<pending>` EXTERNAL-IP you'd get from
`LoadBalancer` on plain kind (no cloud LB controller) — note the path is
`service.spec.type`, not `service.type` (chart 41.x moved raw Service overrides
under `service.spec`). Find the assigned port:

```sh
kubectl -n traefik get svc traefik
```

## 4a. Deploy with Kustomize (no Argo CD)

```sh
kubectl apply -k infra/kubernetes/overlays/kind
kubectl -n totp-manager get pods -w
```

Expected: `totp-psql-0` + `totp-psql-1` Running → `totp-migrate-*` Completed →
`totp-manager-*` Ready.

Without Argo CD, `totp-migrate`'s `PreSync`/`hook-delete-policy` annotations
are just inert labels — plain `kubectl apply -k` runs it once as an ordinary
Job. On a schema change, delete it yourself before re-applying:
```sh
kubectl -n totp-manager delete job totp-migrate --ignore-not-found
kubectl apply -k infra/kubernetes/overlays/kind
kubectl -n totp-manager wait --for=condition=complete job/totp-migrate --timeout=120s
```

Check the operator picked up the cluster:

```sh
kubectl -n totp-manager get postgresql
kubectl -n totp-manager get secret totp.totp-psql.credentials.postgresql.acid.zalan.do
```

## 4b. Deploy with Argo CD

Argo CD reads from git — push `master` first (`infra/argocd/application.yaml`
already points `targetRevision` at it).

```sh
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server

kubectl apply -f infra/argocd/postgres-operator.yaml   # wait until Healthy
kubectl apply -f infra/argocd/application.yaml
kubectl -n argocd get applications -w
```

UI:

```sh
kubectl -n argocd port-forward svc/argocd-server 8081:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

## 5. Reach the app

**Via Traefik** (add `127.0.0.1 totp.local` to `/etc/hosts`, use the NodePort from step 3):

```sh
kubectl -n traefik get svc traefik            # note the web (80) nodePort
kubectl -n traefik port-forward svc/traefik 8080:80
curl -H 'Host: totp.local' http://localhost:8080/health
```

**Without Traefik** (skip step 3):

```sh
kubectl -n totp-manager port-forward svc/totp-manager 8000:8000
curl http://localhost:8000/health
```

## 6. Schema changes later

1. edit `models.py`
2. `alembic revision --autogenerate -m "..."` against a local Postgres, commit the file in `alembic/versions/`
3. rebuild the image with a new tag, bump `newTag` in `overlays/kind/kustomization.yaml`
4. sync — the `PreSync` hook reruns `totp-migrate` before the new app pods roll out

## Notes / limits

- **`ENCRYPTION_KEY`** is the master Fernet key — losing it makes every stored TOTP secret unrecoverable. Back it up outside the cluster.
- **`overlays/kind/secret.yaml`** is sops+age encrypted (see above) — safe to commit even to a public repo. The one thing that must never land in git is the age *private* key (`~/.config/sops/age/keys-totp-own.txt` + the `sops-age` Secret in-cluster).
- **Pod anti-affinity is OFF** for the operator. With kind's node-pinned `local-path` PVs, turning it on can wedge a replica in `Pending` during the operator's rolling updates (volume node-affinity vs anti-affinity conflict). The 2 instances still spread across the `cka` workers via the default scheduler.
- **No TLS yet** — `base/ingress.yaml` is plain HTTP. Add `spec.tls` + a `kubernetes.io/tls` Secret (cert-manager + a `cert-manager.io/cluster-issuer` annotation is the usual path — cert-manager's ingress-shim watches `Ingress` objects directly, no Gateway API integration needed) when this goes further than local testing.
- **GeoIP** database is baked into the image at build time (`GEOIP_URL` build arg). Rebuild to refresh.
- **Rate limiting** (`slowapi`) is in-memory per pod. Fine at 1 replica; point it at Redis before scaling out.
- **`X-Forwarded-For`** is trusted from any caller in `main.py` — only expose the app behind Traefik.
