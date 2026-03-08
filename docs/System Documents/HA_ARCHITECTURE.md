# TelsonBase High Availability Architecture

**Version:** v11.0.1 · **Maintainer:** Quietfire AI
**Status:** Planning Document
**Applies to:** TelsonBase v11.0.1

---

## Table of Contents

1. [Current Architecture](#1-current-architecture)
2. [Phase 1: Docker Swarm](#2-phase-1-docker-swarm)
3. [Phase 2: Kubernetes](#3-phase-2-kubernetes)
4. [Component-Specific HA Strategies](#4-component-specific-ha-strategies)
5. [Data Replication Matrix](#5-data-replication-matrix)
6. [Self-Hosted Deployment Considerations](#6-self-hosted-deployment-considerations)
7. [Decision Matrix](#7-decision-matrix)

---

## 1. Current Architecture

### Single-Node Docker Compose Deployment

TelsonBase runs as a single-host Docker Compose stack. All services execute on one machine, communicating over five segmented bridge networks (frontend, backend, data, ai, monitoring).

#### Service Inventory

| Service | Image | Role | Networks |
|---------|-------|------|----------|
| **traefik** | traefik:v2.10 | TLS termination, reverse proxy, HSTS, security headers | frontend, backend |
| **mcp_server** | Custom (Dockerfile) | FastAPI application server, 100+ endpoints, JWT auth | frontend, backend, data, ai |
| **worker** | Custom (Dockerfile) | Celery task worker, background processing | backend, data, ai |
| **beat** | Custom (Dockerfile) | Celery Beat scheduler | backend, data |
| **redis** | redis:7-alpine | Session store, rate limiting, audit chain, 9 persistence stores | data |
| **postgres** | postgres:16-alpine | Durable storage (users, audit entries, tenants, compliance records) | data |
| **ollama** | ollama/ollama | Local LLM inference (sovereign AI) | ai |
| **mosquitto** | eclipse-mosquitto:2 | MQTT event bus for agent communication | data |
| ~~**n8n**~~ | - | **Removed** - replaced by MCP gateway at `/mcp` (v8.0.2, Feb 2026) | - |
| **open-webui** | ghcr.io/open-webui/open-webui | Human-AI chat interface | frontend, ai |
| **prometheus** | prom/prometheus:v2.49.1 | Metrics collection, alert rules | monitoring, backend |
| **grafana** | grafana/grafana:10.3.1 | Metrics visualization, dashboards | monitoring, frontend |

#### Network Segmentation

The current deployment uses five isolated Docker bridge networks to limit lateral movement:

- **frontend** -- Public-facing services (Traefik, mcp_server incl. `/mcp` gateway, Open-WebUI, Grafana)
- **backend** -- Internal service mesh (mcp_server, worker, Traefik, Prometheus)
- **data** -- Database tier, internal only (Redis, PostgreSQL, Mosquitto)
- **ai** -- Inference tier, internal only (Ollama)
- **monitoring** -- Observability tier, internal only (Prometheus, Grafana)

#### Single Point of Failure Analysis

| SPOF | Impact | Severity |
|------|--------|----------|
| **Host machine** | Total service outage | Critical |
| **Docker daemon** | Total service outage | Critical |
| **PostgreSQL instance** | No durable writes, user/tenant operations fail | High |
| **Redis instance** | No sessions, rate limiting, audit chain writes fail; in-memory fallback for rate limiting only | High |
| **Traefik instance** | No external HTTPS access | High |
| **Ollama instance** | No LLM inference; API endpoints return degraded responses | Medium |
| **Mosquitto instance** | No MQTT event bus; agent communication interrupted | Medium |
| **Single disk/volume** | Data loss for any service whose volume resides on failed disk | Critical |

#### Current Availability Characteristics

- **Availability model:** Dependent entirely on host uptime and Docker daemon stability.
- **Recovery mechanism:** Docker `restart: always` policies handle process crashes. Host-level failures require manual intervention.
- **RPO (current):** 24 hours for backups (scripts/backup.sh: pg_dump + Redis BGSAVE + secrets tar). Redis AOF provides sub-second durability for in-flight data between backups.
- **RTO (current):** Approximately 15 minutes for restore from backup (scripts/restore.sh). Cold-start time for full stack is approximately 2-3 minutes.
- **Monitoring:** Prometheus alert rules detect HighErrorRate, HighLatency, AuthFailureSpike, AuditChainBroken, and ServiceDown conditions. Alerting depends on a functioning Prometheus instance on the same host.

---

## 2. Phase 1: Docker Swarm

### Recommended First Step Toward HA

Docker Swarm is the natural progression from Docker Compose. The existing `docker-compose.yml` is largely compatible with Swarm mode, and the `deploy:` blocks already present (resource limits, reservations) are Swarm-native directives.

### Architecture Overview

```
                    +-----------+
                    |  Clients  |
                    +-----+-----+
                          |
                    Swarm Ingress (ports 80, 443)
                          |
            +-------------+-------------+
            |             |             |
       +----+----+  +----+----+  +----+----+
       | Node 1  |  | Node 2  |  | Node 3  |
       | Manager |  | Manager |  | Worker  |
       +---------+  +---------+  +---------+
       | traefik |  | traefik |  |         |
       | mcp (x1)|  | mcp (x1)|  | mcp(x1)|
       | worker  |  | worker  |  | worker  |
       | beat    |  |         |  |         |
       | redis   |  | redis-s |  | redis-s |
       | pg-pri  |  | pg-stby |  |         |
       | mosquit.|  |         |  |         |
       | ollama  |  |         |  | ollama  |
       | prom    |  |         |  |         |
       | grafana |  |         |  |         |
       +---------+  +---------+  +---------+
```

### Conversion Steps

1. **Initialize Swarm.** On the primary node, run `docker swarm init`. Join additional nodes with the generated token.

2. **Convert Compose file.** Rename or copy `docker-compose.yml` to a stack file. Replace `build:` directives with pre-built image references (push images to a private registry or use `docker save`/`docker load` across nodes).

3. **Deploy as stack.** Use `docker stack deploy -c docker-compose.yml telsonbase`.

4. **Scale stateless services.** Set `deploy.replicas` for mcp_server and worker:
   ```yaml
   mcp_server:
     deploy:
       replicas: 3
       update_config:
         parallelism: 1
         delay: 10s
         order: start-first
       restart_policy:
         condition: on-failure
         delay: 5s
         max_attempts: 3
   ```

5. **Configure Swarm overlay networks.** Replace bridge networks with overlay networks so services can communicate across nodes:
   ```yaml
   networks:
     frontend:
       driver: overlay
     backend:
       driver: overlay
     data:
       driver: overlay
       internal: true
     ai:
       driver: overlay
       internal: true
     monitoring:
       driver: overlay
       internal: true
   ```

6. **Secrets migration.** Docker Swarm has native secrets management. Convert file-based secrets to Swarm secrets:
   ```bash
   docker secret create telsonbase_mcp_api_key ./secrets/telsonbase_mcp_api_key
   docker secret create telsonbase_jwt_secret ./secrets/telsonbase_jwt_secret
   docker secret create telsonbase_encryption_key ./secrets/telsonbase_encryption_key
   docker secret create telsonbase_encryption_salt ./secrets/telsonbase_encryption_salt
   docker secret create telsonbase_grafana_password ./secrets/telsonbase_grafana_password
   ```

### Stateful Service Placement

Stateful services (PostgreSQL, Redis, Mosquitto, Ollama) must be pinned to specific nodes using placement constraints:

```yaml
postgres:
  deploy:
    placement:
      constraints:
        - node.labels.postgres == primary
```

### Load Balancing

- **Swarm ingress mesh** provides automatic round-robin load balancing for published ports across all nodes.
- **Traefik** continues to handle TLS termination, HSTS, and security headers. In Swarm mode, Traefik discovers services via Docker socket and routes based on labels already defined in the current compose file.
- **Health check routing** ensures Traefik only sends traffic to healthy mcp_server replicas. The existing healthcheck configuration (`curl -f http://localhost:8000/`) is preserved.

### Prerequisites

| Requirement | Details |
|-------------|---------|
| Shared storage | NFS share or Drobo volume accessible from all nodes for persistent volumes (postgres_data, redis_data, etc.) |
| Private registry | Harbor, Docker Registry, or `docker save`/`load` workflow for custom images (mcp_server, worker, beat) |
| Internal network | All Swarm nodes must communicate on ports 2377 (cluster management), 7946 (node communication), 4789/UDP (overlay network) |
| DNS or VIP | A single entry point (floating IP or DNS round-robin) for client access |

### Estimated Effort

- **Duration:** 2-3 days
- **Code changes:** Minimal. Replace `build:` with `image:` references. Add `deploy.replicas` and placement constraints. Convert bridge networks to overlay.
- **Risk:** Low. Swarm mode is a superset of Compose; rollback is straightforward.
- **Testing:** Validate that mcp_server replicas share the same Redis and PostgreSQL state. Confirm JWT tokens issued by one replica are accepted by another (they will be, as auth is stateless with shared secret).

---

## 3. Phase 2: Kubernetes

### For Larger Deployments and SLA Requirements

Kubernetes provides declarative infrastructure, automated scaling, self-healing, and a mature ecosystem for production operations. This phase is recommended when the deployment exceeds what Docker Swarm can manage operationally, or when contractual SLAs demand more sophisticated orchestration.

### Helm Chart Structure

```
telsonbase-chart/
  Chart.yaml
  values.yaml
  templates/
    _helpers.tpl
    namespace.yaml
    configmap.yaml
    secrets.yaml
    # Stateless workloads
    deployment-mcp-server.yaml
    deployment-worker.yaml
    deployment-beat.yaml
    # Stateful workloads
    statefulset-postgresql.yaml
    statefulset-redis.yaml
    # Third-party
    deployment-traefik.yaml        (or use Traefik Helm subchart)
    deployment-mosquitto.yaml
    deployment-ollama.yaml
    # deployment-n8n.yaml  # REMOVED - replaced by MCP gateway on mcp_server
    deployment-open-webui.yaml
    deployment-prometheus.yaml     (or use kube-prometheus-stack subchart)
    deployment-grafana.yaml        (or use kube-prometheus-stack subchart)
    # Networking
    ingress.yaml
    networkpolicy-data.yaml
    networkpolicy-ai.yaml
    networkpolicy-monitoring.yaml
    # Scaling
    hpa-mcp-server.yaml
    hpa-worker.yaml
    # Storage
    pvc-postgresql.yaml
    pvc-redis.yaml
    pvc-ollama.yaml
    pvc-mosquitto.yaml
    pvc-grafana.yaml
    # pvc-n8n.yaml  # REMOVED - n8n data volume retained locally; not needed in k8s
    pvc-letsencrypt.yaml
  charts/                          (subcharts for Traefik, Prometheus, etc.)
```

### Workload Types

| Component | Kubernetes Resource | Replicas | Notes |
|-----------|-------------------|----------|-------|
| mcp_server | Deployment | 2-N (HPA) | Stateless, JWT auth, horizontal scaling |
| worker | Deployment | 2-N (HPA) | Stateless, scales with task queue depth |
| beat | Deployment | 1 | Singleton scheduler, leader election |
| PostgreSQL | StatefulSet | 2-3 | Primary + standby(s), PVC per pod |
| Redis | StatefulSet | 3 | Sentinel topology, PVC per pod |
| Ollama | Deployment | 1-N | GPU node affinity, resource requests for GPU |
| Mosquitto | StatefulSet | 1 | Or replace with EMQX for native clustering |
| Traefik | Deployment / DaemonSet | 2+ | Or replaced by NGINX Ingress Controller |
| ~~n8n~~ | - | - | **Removed** - MCP gateway runs inside mcp_server pod (no separate deployment) |
| Prometheus | StatefulSet | 1 | PVC for TSDB |
| Grafana | Deployment | 1 | PVC for dashboards and config |

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: mcp-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: mcp-server
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### Persistent Volume Claims

All stateful data uses PersistentVolumeClaims backed by the cluster's StorageClass. For self-hosted deployments, this is typically an NFS provisioner or a local-path provisioner.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: postgresql-data
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: nfs-client
  resources:
    requests:
      storage: 50Gi
```

### Ingress with TLS Termination

Kubernetes Ingress replaces Traefik's current role (or Traefik is deployed as the Ingress Controller):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: telsonbase-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/hsts: "true"
    nginx.ingress.kubernetes.io/hsts-max-age: "31536000"
    nginx.ingress.kubernetes.io/hsts-include-subdomains: "true"
    nginx.ingress.kubernetes.io/hsts-preload: "true"
spec:
  tls:
    - hosts:
        - telsonbase.com
      secretName: telsonbase-tls
  rules:
    - host: telsonbase.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: mcp-server
                port:
                  number: 8000
```

### Network Policies

The current five-network segmentation maps to Kubernetes NetworkPolicy resources, preserving the same isolation model:

- **data** tier: Only mcp_server, worker, and beat pods can reach PostgreSQL and Redis.
- **ai** tier: Only mcp_server, worker, and open-webui pods can reach Ollama.
- **monitoring** tier: Only Prometheus can scrape backends; only Grafana can query Prometheus.

### Estimated Effort

- **Duration:** 1-2 weeks
- **Code changes:** Application code is unchanged. All work is in Kubernetes manifests and Helm chart authoring.
- **Risk:** Medium. Requires Kubernetes operational knowledge. Consider managed Kubernetes (k3s for self-hosted) to reduce cluster management overhead.
- **Prerequisites:** Container registry, Kubernetes cluster (k3s recommended for self-hosted), NFS or equivalent storage provisioner, cert-manager for TLS.

---

## 4. Component-Specific HA Strategies

### PostgreSQL

| Strategy | Description |
|----------|-------------|
| **Streaming replication** | Asynchronous or synchronous WAL shipping from primary to one or more standby nodes. Built into PostgreSQL 16. |
| **pgpool-II** | Connection pooler and load balancer. Routes reads to standbys, writes to primary. Provides automatic failover detection. |
| **Automatic failover** | Patroni (recommended) or repmgr for automated promotion of standby to primary on failure detection. |
| **Backup integration** | WAL archiving to shared storage or S3-compatible object store for point-in-time recovery. Supplements the existing pg_dump-based backup in scripts/backup.sh. |

Recommended stack for Phase 1: PostgreSQL streaming replication (1 primary, 1 standby) with manual failover. For Phase 2: Patroni with etcd for automatic failover.

### Redis

| Strategy | Description |
|----------|-------------|
| **Redis Sentinel** | 3-node Sentinel deployment monitors the master and performs automatic failover. Sentinels agree on master election via quorum. |
| **AOF persistence** | Already configured (`appendonly yes`, `appendfsync everysec`). Provides sub-second durability. |
| **Replica nodes** | 1-2 read replicas for the 9 persistence stores (ComplianceStore, SecurityStore, TenancyStore, etc.). |

Application changes required: Update `core/config.py` Redis connection to use Sentinel-aware client (`redis.sentinel.Sentinel`) instead of direct host connection. The `redis-py` library supports this natively.

### Traefik

| Strategy | Description |
|----------|-------------|
| **Docker Swarm mode** | Traefik natively integrates with Swarm. Multiple Traefik instances share configuration via Docker service discovery. |
| **Health check routing** | Traefik routes only to healthy mcp_server instances using the existing Docker healthcheck. |
| **Sticky sessions** | Not required. mcp_server is stateless (JWT-based auth, shared Redis session store). |
| **Certificate storage** | In Swarm/K8s, ACME certificate storage must use a shared backend (Consul, etcd, or file on shared volume) instead of local file. |

### Celery Workers

| Strategy | Description |
|----------|-------------|
| **Horizontal scaling** | Workers are stateless. Scale by increasing `deploy.replicas`. Each worker connects to the same Redis broker. |
| **Task routing** | Use Celery task queues to separate workload types (e.g., backup tasks, compliance checks, AI inference tasks) across dedicated worker pools. |
| **Beat singleton** | Celery Beat must run as a single instance. In Kubernetes, use a Deployment with `replicas: 1` and leader election. In Swarm, use `deploy.replicas: 1` with a placement constraint. |

### mcp_server (FastAPI)

| Strategy | Description |
|----------|-------------|
| **Stateless design** | Authentication is JWT-based. Sessions are stored in Redis. No local state. Any replica can handle any request. |
| **Horizontal scaling** | Scale replicas behind Traefik or Kubernetes Ingress. No session affinity required. |
| **Graceful shutdown** | FastAPI handles SIGTERM for graceful connection draining. Configure `stop_grace_period` in Compose/Swarm. |
| **Health endpoint** | Existing `GET /` healthcheck serves as readiness and liveness probe. |

### MQTT (Mosquitto)

| Strategy | Description |
|----------|-------------|
| **Mosquitto bridging** | Configure bridge connections between Mosquitto instances on different nodes. Messages are forwarded across the bridge. Suitable for 2-3 nodes. |
| **EMQX replacement** | For native clustering beyond 3 nodes, replace Mosquitto with EMQX. EMQX supports automatic cluster formation, shared subscriptions, and horizontal scaling. EMQX is open-source and Docker-ready. |
| **Retained messages** | Retained messages must be replicated. Mosquitto bridging handles this; EMQX handles it natively via Mnesia. |

Application impact: The MQTT client in `core/mqtt_bus.py` connects by hostname. Switching to EMQX requires no code changes if the MQTT endpoint is updated in configuration.

### Ollama

| Strategy | Description |
|----------|-------------|
| **GPU-bound workload** | Ollama requires GPU (or significant CPU) resources. It cannot be scaled the same way as stateless services. |
| **Dedicated inference nodes** | Deploy Ollama on separate nodes with GPU hardware. Use node labels and placement constraints to pin Ollama to GPU nodes. |
| **Request routing** | Place a load balancer in front of multiple Ollama instances. Route inference requests round-robin. Model loading is per-instance, so all instances must have the same models loaded. |
| **Shared model storage** | Mount model data (`ollama_data` volume) from shared NFS to avoid downloading models on every node. |

---

## 5. Data Replication Matrix

| Component | Data Type | Replication Method | RPO | RTO | Notes |
|-----------|-----------|-------------------|-----|-----|-------|
| **PostgreSQL** | Users, tenants, audit entries, compliance records | Streaming replication (sync) | ~0 (synchronous mode) | < 30s (automatic failover with Patroni) | 4 tables: users, audit_entries, tenants, compliance_records |
| **Redis** | Sessions, rate limits, audit chain, 9 persistence stores | Sentinel + AOF | < 1s | < 30s (Sentinel master election) | appendfsync everysec already configured |
| **Audit Chain** | Cryptographic hash-linked audit entries | Redis sorted sets (primary) + PostgreSQL (durable) | ~0 | < 1 min | Dual-write: Redis for performance, PostgreSQL for durability |
| **Backups** | Full system snapshots (pg_dump + Redis BGSAVE + secrets) | Shared storage / S3-compatible | 24 hr | 15 min (restore.sh) | Current: scripts/backup.sh, scripts/restore.sh |
| **TLS Certificates** | Let's Encrypt ACME certificates | Shared volume (letsencrypt_data) | N/A (re-issuable) | < 5 min (ACME re-issue) | Store acme.json on shared storage in multi-node |
| **Grafana Dashboards** | Dashboard JSON, provisioning configs | Bind-mounted from repo (monitoring/grafana/) | N/A (version controlled) | < 1 min (redeploy) | Dashboards are code, stored in git |
| **Mosquitto** | MQTT retained messages, QoS 1/2 in-flight | Bridge replication or EMQX Mnesia | < 1s (bridge) | < 30s | Agent communication state |

### Replication Priority Order

1. **PostgreSQL** -- Contains authoritative records (users, compliance, tenants). Loss is unacceptable.
2. **Redis** -- Contains active sessions, rate limiting state, and the audit chain working set. Loss causes service disruption.
3. **Audit Chain** -- Dual-written to both Redis and PostgreSQL. PostgreSQL is the recovery source.
4. **Backups** -- Last line of defense. Must be stored off-host (NAS, S3, or separate physical media).

---

## 6. Self-Hosted Deployment Considerations

### Data Sovereignty

TelsonBase's primary market is law firms where attorney-client privilege demands that data never leaves the firm's network. All HA strategies must preserve this constraint:

- No cloud dependency. All components run on-premises.
- No external SaaS for any data path (monitoring, logging, backups).
- DNS resolution can use external providers, but all data flows remain internal.
- Ollama provides sovereign AI inference -- no API calls to OpenAI, Anthropic, or other cloud LLM providers.

### Storage Architecture

| Storage Type | Recommended Hardware | Purpose |
|-------------|---------------------|---------|
| **Primary NAS** | Drobo (existing), Synology, or QNAP with RAID | Docker named volumes via NFS shares. PostgreSQL data, Redis AOF, backups. |
| **Secondary NAS** | Separate physical device | Backup target. Receives daily backup archives from scripts/backup.sh. |
| **Local SSD** | Per-node NVMe or SSD | Ollama model cache (performance-sensitive). Docker image layers. |

#### NFS Configuration for Multi-Node Volumes

For Docker Swarm or Kubernetes, named volumes must be accessible from all nodes. NFS is the simplest approach for self-hosted deployments:

```yaml
volumes:
  postgres_data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=192.168.1.100,rw,nfsvers=4
      device: ":/exports/telsonbase/postgres"
```

**Warning:** PostgreSQL on NFS requires careful tuning. Set `synchronous_commit = on` and ensure the NFS server has battery-backed write cache or use `sync` mount option. Alternatively, keep PostgreSQL on local storage and use streaming replication instead of shared storage.

### Minimum Hardware Requirements

| Configuration | Nodes | Purpose | Minimum Specs Per Node |
|---------------|-------|---------|----------------------|
| **Meaningful HA** | 2 | 1 primary, 1 hot standby | 8 CPU cores, 32 GB RAM, 500 GB SSD |
| **Production HA** | 3 | 2 managers + 1 worker (Swarm) | 8 CPU cores, 32 GB RAM, 500 GB SSD |
| **With GPU inference** | 3+ | Add dedicated Ollama node(s) | Ollama node: 8 CPU, 32 GB RAM, NVIDIA GPU (8+ GB VRAM) |

Resource budget based on current `docker-compose.yml` resource reservations:

| Service | CPU Reserved | Memory Reserved |
|---------|-------------|-----------------|
| mcp_server | 0.5 | 256 MB |
| worker | 0.7 | 512 MB |
| beat | 0.1 | 64 MB |
| redis | 0.2 | 64 MB |
| postgres | 0.2 | 128 MB |
| ollama | 1.0 | 4 GB |
| mosquitto | 0.1 | 64 MB |
| ~~n8n~~ | - | - |
| open-webui | 0.3 | 128 MB |
| prometheus | 0.2 | 128 MB |
| grafana | 0.2 | 128 MB |
| **Total** | **4.0** | **5.7 GB** |

A single 8-core / 32 GB node comfortably hosts the full stack with headroom for spikes. Two such nodes provide failover capacity.

### Networking

| Requirement | Specification |
|-------------|--------------|
| **Inter-node bandwidth** | Gigabit Ethernet minimum. PostgreSQL streaming replication and Redis Sentinel heartbeats require low-latency connectivity. |
| **Swarm ports** | TCP 2377 (cluster management), TCP/UDP 7946 (node discovery), UDP 4789 (VXLAN overlay) |
| **Firewall** | Block Swarm/K8s management ports from external access. Only ports 80 and 443 should be externally reachable. |
| **Multi-site** | If nodes are in separate physical locations, use a site-to-site VPN (WireGuard recommended). Latency under 10ms is required for synchronous PostgreSQL replication. |
| **DNS** | Internal DNS or `/etc/hosts` entries for node discovery. External DNS for telsonbase.com pointing to the primary node or a floating VIP. |

---

## 7. Decision Matrix

### When to Use Which Approach

| User Scale | Recommended Architecture | Justification |
|-----------|-------------------------|---------------|
| **1-10 users** | Single node (current) | Docker `restart: always` policies provide process-level recovery. Daily backups (RPO 24hr) are acceptable. Operational simplicity outweighs HA benefits. |
| **10-50 users** | Docker Swarm (Phase 1) | Multi-node provides host-level failover. Swarm ingress distributes load. PostgreSQL streaming replication and Redis Sentinel protect data. Effort is 2-3 days. |
| **50+ users or SLA requirements** | Kubernetes (Phase 2) | HPA auto-scaling handles variable load. Pod disruption budgets guarantee availability during updates. NetworkPolicy enforces the existing five-zone segmentation model. Required for contractual uptime SLAs (99.9%+). |

### Decision Factors Beyond User Count

| Factor | Single Node | Docker Swarm | Kubernetes |
|--------|-------------|--------------|------------|
| **Contractual SLA** | None (best-effort) | Informal (99.5%) | Formal (99.9%+) |
| **Operational expertise required** | Docker Compose | Docker Swarm (incremental) | Kubernetes (significant) |
| **Recovery from host failure** | Manual restore (15 min RTO) | Automatic failover (< 1 min) | Automatic failover (< 30s) |
| **Rolling updates** | Downtime during redeploy | Zero-downtime (start-first) | Zero-downtime (rolling) |
| **Cost (hardware)** | 1 server | 2-3 servers | 3+ servers |
| **Cost (operational)** | Low | Low-Medium | Medium-High |
| **Compliance posture** | Acceptable for pilot | Production-ready | Enterprise-grade |
| **Auto-scaling** | None | Manual replica count | Automatic (HPA) |

### Recommended Path

For TelsonBase's current trajectory (law firm pilots, self-hosted, compliance-driven):

1. **Now:** Continue with single-node deployment. Focus on completing Cluster C hardening items (SOC 2 documentation, pen test prep, disaster recovery testing).

2. **First paying customer:** Implement Phase 1 (Docker Swarm) with 2 nodes. This provides meaningful HA with minimal disruption to the existing architecture and operational model.

3. **5+ firm deployments or enterprise contract:** Evaluate Phase 2 (Kubernetes) based on operational requirements. Consider k3s for a lightweight self-hosted Kubernetes distribution that aligns with the on-premises deployment model.

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **RPO** | Recovery Point Objective -- maximum acceptable data loss measured in time |
| **RTO** | Recovery Time Objective -- maximum acceptable downtime from failure to recovery |
| **SPOF** | Single Point of Failure -- a component whose failure causes system-wide outage |
| **WAL** | Write-Ahead Log -- PostgreSQL's transaction log used for replication and recovery |
| **AOF** | Append-Only File -- Redis persistence mechanism that logs every write operation |
| **HPA** | Horizontal Pod Autoscaler -- Kubernetes resource that scales pods based on metrics |
| **PVC** | PersistentVolumeClaim -- Kubernetes abstraction for requesting durable storage |
| **VIP** | Virtual IP -- a floating IP address that moves between nodes for seamless failover |

## Appendix B: Related Documents

- `docs/BACKUP_RECOVERY.md` -- Current backup and restore procedures (RPO 24hr, RTO 15min)
- `docs/SECRETS_MANAGEMENT.md` -- Secret generation, rotation, and validation
- `docs/ENCRYPTION_AT_REST.md` -- Volume-level encryption (LUKS/BitLocker) and compliance mapping
- `.github/workflows/ci.yml` -- CI/CD pipeline (test, docker-build, security-scan)
- `monitoring/prometheus/alerts.yml` -- Prometheus alert rules (HighErrorRate, ServiceDown, etc.)
- `monitoring/grafana/dashboards/telsonbase_overview.json` -- Grafana dashboard

---

*TelsonBase v11.0.1 · Quietfire AI · March 8, 2026*
