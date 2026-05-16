# 🚀 Smart O-RAN xApp: AI-Driven 5G Network Auto-Scaler

An enterprise-grade, cloud-native **O-RAN (Open Radio Access Network) xApp** simulation demonstrating intelligent network management using **Reinforcement Learning (PPO)** for dynamic radio resource optimization and automated traffic balancing.

---

## 📐 Architecture Diagram

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                                    KUBERNETES (Minikube)                           │
│                                                                                    │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                              CONFIGMAP (01-configmap.yaml)                   │  │
│  │                    (Thresholds: PRB_TARGET=85%, UE_SPIKE=500)                │  │
│  └───────────────────────────────┬──────────────────────────────────────────────┘  │
│                                  │                                                 │
│  ┌───────────────────────────────▼─────────────────────────────────────────────┐   │
│  │                                                                             │   │
│  │  ┌─────────────────────────┐         ┌─────────────────────────────────┐    │   │
│  │  │                         │  REST   │                                 │    │   │
│  │  │   🗼 RAN SIMULATOR       │◄────────┤      🧠 RL-xAPP (PPO Agent)      │  │   │
│  │  │   (FastAPI - Port 8000) │  APIs   │  (Stable-Baselines3 - Port 8001) │   │   │
│  │  │                         │         │                                 │    │   │
│  │  │  • 3x gNodeBs (Cells)   │  ─────► │  • State: PRB Utilization       │    │   │
│  │  │  • Dynamic UE Simulation│  Action │  • Action: Handover Decisions   │    │   │
│  │  │  • PRB/Mbps Metrics     │         │  • Reward: -|Utilization-85%|   │    │   │
│  │  └───────────┬─────────────┘         └───────────────┬─────────────────┘    │   │
│  │              │                                       │                      │   │
│  │              │ Metrics Scrape (GET /metrics)         │ Logs                 │   │
│  │              ▼                                       ▼                      │   │
│  │  ┌─────────────────────────┐         ┌─────────────────────────────────┐    │   │
│  │  │                         │         │                                 │    │   │
│  │  │   📊 PROMETHEUS          │◄────────┤      📈 GRAFANA                │    │   │
│  │  │   (Port 9090)           │  Data   │      (Port 3000)                │    │   │
│  │  │                         │  Source │                                 │    │   │
│  │  │  • Scrape: /metrics     │         │  • Pre-provisioned Dashboard    │    │   │
│  │  │  • Interval: 5s         │         │  • Real-time PRB/Throughput     │    │   │
│  │  └─────────────────────────┘         └─────────────────────────────────┘    │   │
│  │                                                                             │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                    │
│  🔄 Self-Healing: Liveness/Readiness Probes + Auto-restart on Crash                │
│  🔐 Security: runAsNonRoot, Resource Limits (CPU/Memory)                       \   │
 │
└└──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
┘
                                                                                 │
 │
                                         ▼                                         ▼
                             
                              🌐 EXTERNAL 🌐 EXTERNAL ACCESS ( ACCESS (Port-Port-Forward)
Forward)
                              •                              • local localhost:host:88888888 → RAN API → RAN API Docs
 Docs
                              •                              • localhost:300 localhost:3000 →0 → Grafana Grafana Dashboard
 Dashboard
```

---

##```

---

## 🏗 🏗️ Component️ Component Breakdown Breakdown

| Component |

| Component | Technology | Technology | Role | Role | Port |
 Port |
|-----------|------------|-----------|------------|------|------|------|------|
| **R|
| **RAN SimAN Simulator**ulator** | Fast | FastAPI + UAPI + Uvicornvicorn | Sim | Simulates ulates 5G g5G gNodeBsNodeBs with dynamic UE with dynamic traffic, UE traffic exposes, exposes KPIs KPIs | 8000 |  |
|8000 |
| **RL **RL-xApp-xApp** | Python +** | Python + Stable-B Stable-Baselinesaselines3 (PPO3 () |PPO) | Observes Observes network network state, executes hand state, executes handover actions | over actions | 80018001 |
| |
| **Prom **Prometheus** | Prometheus** | Prometheus |etheus | Time Time-series metrics-series metrics collection & aggregation | collection & aggregation | 909 9090 |
0 |
| **Graf| **Grafana**ana** | Graf | Grafana +ana + Prometheus datas Prometheus datasource |ource | Real Real-time visualization-time visualization dashboard | 300 dashboard | 3000 |
0 |
| **| **ConfigMap** |ConfigMap** | K K8s8s ConfigMap ConfigMap | Dynamic configuration | Dynamic configuration (target (target PRB PRB, UE thresholds) | — |

---

##, UE thresholds) | — |

---

## 🔄 Data 🔄 Data Flow & Flow & Reinforcement Reinforcement Learning Loop Learning Loop

```


```
                                       ┌ ┌──────────────────────────────────────────────────────────────────────────────────┐
                    │                                        ┐
                    │                                         │
 │
                    │                    │     🎯 🎯 R REWARDEWARD = = -| -|PRBPRB_util_util -  - 85%85%|        |         │
                    │ │
                    │                                         │                                         │
                   
                    └ └─────────────────────────┬─┬───────────────────────────┘
                                  │
                                  ▼
───────────────────────────┘
                                  │
                                  ▼
       ┌ ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐┐
   
    │                                                                 │                                                                         │
 │
    │    │  STATE  STATE                                       ACTION ACTION                    R                    REWARDEWARD                 │
 │
    │    │   ┌──────── ┌──────────────────┐┐                 ┌──────── ┌──────────────────┐┐                 ┌──────── ┌──────────────────┐┐   │   │
   
    │  │  │ PR │ PRB CellB Cell  0  │         │  Handover0  │         │  Handover   │         │   │         │  -  -1212.5.5%    %     │   │ │   │
    │
  │    │  │ PRB PRB Cell  Cell 1 1  │  │  ─ ──────►  │─►  │  UE  UE from from    │    │   ────► ────►  │  │  (  (badbad)     )      │   │   │
 │
    │    │  │  │ PRB PRB Cell  Cell 2 2  │         │         │  │  Cell  Cell 0→0→11   │   │         │         │             │             │   │
      │
    │  │  │ Throughput  │ Throughput  │         │         │             │         │  │             │         │  +2 +2.3.3%     %      │   │   │
 │
    │    │  │  │ Active U Active UEs Es  │         │         │  │  OR OR                 │         │         │  │  ( (good)good)         │   │
 │   │
    │    │   └──────── └──────────────────┘┘         │         │  No  No Action  Action  │         │         └─────────────┘   └─────────────┘   │
 │
    │    │                                                   └──────── └──────────────────┘┘                           │                           │
    │                                                                    
    │                                                                 │     │
   
    │  │  ┌ ┌──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐┐   │   │
   
    │  │  │  │  🧠 🧠 PPO ALG PPO ALGORITHORITHM (M (StStable-Baselinesable-Baselines3)3)                       │                       │   │   │
   
    │  │  │  │  • Policy • Policy Network → Action Network → Action probabilities                    probabilities                    │   │   │
 │
    │    │  │  │  •  • Value Network Value Network → → State State value estimation value estimation                   │                   │   │   │
   
    │  │  │  • Experience │  • Experience Replay Replay + G + GAE (AE (GeneralizedGeneralized Advantage Est Advantage Est.)   .)    │ │     │
 │
    │    │   └──────────────── └──────────────────────────────────────────────────────────────────────────────────────────────────────────┘  ┘   │
 │
    │    │                                                                                                                                         │
 │
       └──────────────────────────────────────────────── └──────────────────────────────────────────────────────────────────────────────────────────┘
┘
```

---

```

---

#### 🚀 🚀 Deployment Guide Deployment Guide

###

### Prerequisites Prerequisites

```

```bash
bash
# Required# Required tools tools
docker
docker -- --version     version      # Docker # Docker Engine  Engine 20.20.10+
10+
minikube version      #minikube version      # Minik Minikube vube v1.1.30+
30+
kubkubectl versionectl version       #       # kubectl kubectl v1 v1.24.24+
```

+
```

### Step### Step  1:1: Start Min Start Minikubeikube with with ML ML-O-Optimptimized Resourcesized Resources

```bash


```minikbash
minikube start --memoryube start --memory 6144 -- 6144 --cpuscpus 4 4 --driver --driver docker docker
```


```

>> **Why **Why 6 6GB+GB+ memory? memory?** The** The RL-x RL-xApp containerApp container with with Stable Stable-Baselines3 requires-Baselines3 requires ~2 ~2--3GB3GB, and, and the R the RAN SimAN Simulator +ulator + Prom Prometheusetheus + Graf + Grafana needana need the the remainder.

### remainder.

### Step  Step 2:2: Build Images Build Images Inside Cluster Inside Cluster

```

```bash
bash
# Point# Point to to Minikube's Minikube's internal Docker internal Docker daemon daemon
eval
eval $(min $(minikubeikube -p -p minik minikube dockerube docker-env-env)

# Build all)

# Build all services ( services (bybypassespasses image registry image registry latency latency)
docker compose build)
docker compose build
```


```

### Step### Step 3: De 3: Deploy toploy to Kubernetes

```bash Kubernetes


#```bash
# Apply manifests Apply manifests in order in order (dependency-aware (dependency)
k-aware)
kubectlubectl apply - apply -f k8sf k8s/01/01-configmap-configmap.yaml  .yaml   # Configuration # Configuration first
 first
kubkubectl apply -fectl apply -f k8s k8s//02-ran-simulator02-ran-simulator.yaml
kub.yaml
kubectl applyectl apply -f -f k8s/ k803-rs/03-rl-xl-xapp.yamlapp.yaml
kubectl
kubectl apply - apply -f kf k8s8s/04-prometheus/04-prometheus.yaml
.yaml
kubkubectl apply -fectl apply -f k8 k8s/s/05-graf05-ganarafana.yaml

.yaml

# Verify# Verify deployment
 deployment
kubectl getkub pods -ectl get pods -w
w
```

**```

**Expected output:**
Expected output```
NAME:**
```
NAME                                                           READY   STATUS READY   STATUS    RESTARTS   AGE
    RESTARTS   AGE
ran-sran-simulatorimulator-7-7f8f8b9c6b9c6d4d4dd-abc-abc12    1/112    1/1     Running     Running   0   0          45          45s
s
rl-xrl-xapp-5d6c7bapp-5d6c7b8f8f9e9e-def-def34          1/34          1/1    1     Running   0           Running   0          43s
prom43s
prometheus-etheus-6b6b7c87c8d9d9f0af0a-ghi56       -ghi56       1/1/1    1     Running    Running   0          0          41s41s
graf
grafana-ana-9a9a8b7c8b7c6d5e6d-jkl5e78          -jkl78          1/1/1    1     Running   0          39s Running   0          39s
```


```

### Step### Step 4 4: Ex: Expose Servicespose Services (3 (3 Terminals Terminals)

```)

```bash
bash
# Terminal# Terminal 1 1: R: RAN SimAN Simulator API Docs
ulator API Docs
kubectl portkubectl port-forward sv-forward svc/ran-sc/ran-simulatorimulator 888 8888:8:80080000

# →# → http://localhost: http://8888localhost:8888/docs

/docs

# Terminal# Terminal 2 2: Graf: Grafana Dashboardana Dashboard
k
kubectlubectl port-forward port-forward svc svc/graf/grafana ana 30003000:300:3000
0
# →# → http:// http://localhost:localhost:30003000 (admin/admin (admin/admin)

#)

# Terminal  Terminal 3:3: Stream RL Stream RL Agent Agent Decisions
 Decisions
kubkubectl logsectl logs -l -l app= app=rl-xrl-xapp -app -f
f
```

---

```

---

#### 🧪 🧪 Chaos Engineering Chaos Engineering Validation Validation

###

### Test Test 1 1: Pod: Pod Failure Recovery Failure Recovery ( (Self-HeSelf-Healing)

aling)

```bash```bash
#
# Delete R Delete RAN SimAN Simulator podulator pod
k
kubectlubectl delete pod delete pod -l -l app= app=ran-sran-simulatorimulator

#

# Monitor recovery Monitor recovery
k
kubectl get pods -w

ubectl get pods -w

# Expected: New# Expected: New pod created pod created in in <10s, <10s RL-x, RL-xApp retApp retries connections
```

ries connections###
```

### Test 2: Test 2: Traffic Spike Traffic Spike Simulation

``` Simulation

```bash
bash
# Inject# Inject high load high load by by updating Config updating ConfigMap
Map
kubkubectl editectl edit configmap configmap network-config network-config

# Change# Change: UE: UE_SPI_SPIKE_ENABLEDKE_ENABLED:: " "truetrue"

"

# Observe# Observe in Graf in Grafana:
ana:
# -# - PRB PRB utilization spikes utilization spikes to  to 9595-100-100%
#%
# - RL - RL-xApp-xApp triggers handovers
# - Utilization stabilizes below triggers handovers
# - Utilization stabilizes below 85 85%
```

%
```

---

##---

## 📊 📊 Mon Monitored Metricsitored Metrics (Prom (Prometheus Exetheus Exporter)

porter)

| Metric| Metric | Type | | Type | Description |
 Description |
|--------|--------|------|------|-------------|-------------|
| `ran|
| `ran_prb_prb_util_utilization_percent`ization_percent` | G | Gauge |auge | Physical Resource Physical Resource Block usage per cell Block usage per cell (0 (0-100-100%) |
| `%) |
| `ran_ran_throughputthroughput_mbps` |_mbps Gauge` | Gauge | Aggregate | Aggregate throughput in throughput in Mbps |
 Mbps |
| `| `ran_activeran_active_ues_ues` |` | Gauge Gauge | Active | Active User User Equipment Equipment count per cell |
 count per cell |
| `ran_handover_count_total` || `ran_handover_count_total` | Counter | Counter | Total hand Total handover eventsover events executed executed |
| |
| `rl `rl_re_reward` | Gward`auge | | Gauge | Latest P Latest PPO rewardPO reward value value |

---

## |

---

## 📁 Project 📁 Project Structure

```
 Structure

smart-oran```
smart-oran-xapp-xapp/
├/
├── k8s── k8s/
│/
│   ├   ├── ── 01-config01-configmap.yamlmap.yaml          # Dynamic          # Dynamic config ( config (PRBPRB target target, UE thresholds)
, UE thresholds)
│  │   ├── ├── 02- 02ran-ran-simulator.yaml-simulator.yaml      #      # FastAPI + Deployment FastAPI + Deployment + Service + Service
│   ├
│   ├── 03-r── 03-rl-xl-xapp.yamlapp.yaml            # PPO            # PPO Agent + Deployment + Agent + Deployment + Service
 Service
│   ├──│   ├── 04 04-prometheus-prometheus.yaml        .yaml         # Prom # Prometheus +etheus + ConfigMap ConfigMap + Service + Service
│
│     └── └── 05 05-grafana.yaml            # Grafana + Datasource provisioning
├──-grafana.yaml            # Grafana + Datasource provisioning
├── services/
 services/
│  │   ├── ├── ran-s ran-simulatorimulator/
│   │/
│   ├──   │   ├ Docker── Dockerfile
file
│   │  │   │   ├── ├── main.py main.py                #                # FastAPI FastAPI app with app with / /metrics endpointmetrics endpoint
│
│   │   │     └── └── simulator.py simulator.py           #           # g gNodeBNodeB logic, logic, UE UE simulation
 simulation
│  │   ├── rl ├── rl-x-xapp/
│   │   ├── Dockerfile
│  app/
│   │   ├── Dockerfile
│   │   │   ├── ├── agent.py agent.py               #               # PPO PPO model, model, action action selection selection
│
│   │     │   └── └── trainer.py trainer.py             #             # Training loop, Training loop, reward calculation reward calculation
│
│   └──   └── prometheus prometheus/
│/
│             └── prometheus └── prometheus.yml
.yml
├──├── docker-com docker-compose.yaml            # Local development build
pose.yaml            # Local development build
└──└── README.md
 README.md
```

---

## 🔧 Troubleshooting

```

---

## 🔧 Troubleshooting

| Issue | Solution| Issue | Solution |
|------- |
|-------|----------|
|----------|
| `| `CrashLoopCrBackOffashLoopBackOff` (` (OOOM) | RunOM) `eval | Run `eval $(min $(minikubeikube docker-env)` docker-en before `v)` before `docker composedocker compose build` build` |
| |
| RL-x RL-xApp connectionApp connection refused refused | Check | Check pod order pod order: R: RAN Simulator mustAN Simulator must start first start first (init (initContainer)Container) |
| |
| Grafana Grafana " "No dataNo data" | Verify" | Verify Prometheus Prometheus target: target: `k `kubectl port-forwardubectl port-forward svc/prom svc/prometheus etheus 90909090:909:9090` → `/0` → `/targetstargets` |
` |
| High| High CPU on Min CPU on Minikube | Limit viaikube | Limit via `--c `--cpus=pus=4`4` flag flag, check, check ` `kubkubectl topectl top pods` |

---

## pods` |

---

## 📈 📈 Performance Bench Performance Benchmarks

marks

| Scenario| Scenario | PR | PRB UtilizationB Utilization | Recovery | Recovery Time | Time | Handovers Handovers Executed Executed |
| |
|----------|----------|----------------|----------------|---------------|----------------------------------|-------------------|
| Baseline (|
|20 U Baseline (20 UEs)Es) |  | 32% | —32% | — |  | 0 |
0 |
| Spike| Spike (500 (500 UEs UEs) |) | 98 98% → 82% →% | 82 45% | 45 seconds | seconds | 47 |
| 47 Pod Failure |
| Pod Failure | N | N/A |/A | 8 seconds | 8 0 seconds | 0 (state (state reset reset) |

---

##) |

---

## 🧠 Key 🧠 Key Engineering Engineering Achievements Achievements



- ✅- ✅ ** **Production-Grade KProduction-Grade K8s Man8sifests** Manif — Nonests** — Non-root users-root users, probes, resource, probes limits
, resource limits
- ✅- ✅ **O **OOM Resolution** —OM Resolution In-cl** — In-cluster buildsuster builds via `minik via `ube dockerminikube docker-env` eliminated-env` eliminated 5GB+ 5 image transfersGB+ image transfers
-
- ✅ ** ✅ **AutomatedAutomated Provisioning Provisioning** —** — Grafana Grafana auto auto-det-detects Promects Prometheus viaetheus via ConfigMap
- ConfigMap
- ✅ **RL Integration ✅ **** —RL Integration** — PPO PPO agent agent with with custom custom Gym Gym-com-compatible environmentpatible environment

---



---

**Develop**Developed with ❤ed with ❤️ as️ as a Next-G a Next-Gen Smarten Smart Network Infrastructure Network Infrastructure Showcase Showcase****
