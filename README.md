# 🚀 Smart O-RAN xApp: AI-Driven 5G Network Auto-Scaler

An enterprise-grade, cloud-native O-RAN (Open Radio Access Network) xApp simulation demonstrating intelligent 5G network management using Reinforcement Learning (PPO) for dynamic radio resource optimization and automated traffic balancing.

---

# 📖 Overview

This project simulates a modern cloud-native 5G O-RAN environment where an AI-powered xApp automatically balances network traffic between multiple gNodeBs.

The system monitors real-time radio metrics such as:

- PRB Utilization
- Throughput
- Active UEs (Users)

Using a PPO Reinforcement Learning agent, the xApp makes autonomous handover decisions to prevent congestion and maintain optimal resource utilization.

---

# 🏗️ System Architecture

```text
+-------------------------------------------------------------+
|                     Kubernetes Cluster                      |
|                         (Minikube)                          |
|                                                             |
|  +-------------------+       +---------------------------+  |
|  |   RAN Simulator   |<----->|      RL xApp (PPO)       |   |
|  |  FastAPI Service  | REST  | Stable-Baselines3 Agent  |   |
|  +-------------------+       +---------------------------+  |
|           |                               |                 |
|           | /metrics                      | Logs            |
|           v                               v                 |
|  +-------------------+       +---------------------------+  |
|  |    Prometheus     |<----->|         Grafana          |   |
|  | Metrics Collector |       | Real-Time Dashboard      |   |
|  +-------------------+       +---------------------------+  |
|                                                             |
+-------------------------------------------------------------+
```

---

# 🧠 Reinforcement Learning Logic

The PPO Agent continuously observes the network state and performs actions to optimize radio resource utilization.

## State

The agent monitors:

- PRB utilization per cell
- Throughput
- Active UE count

## Actions

The xApp can:

- Trigger UE handovers between cells
- Keep the current state unchanged

## Reward Function

The target PRB utilization is 85%.

```math
Reward = -|PRB_Utilization - 85%|
```

The closer the utilization is to 85%, the higher the reward.

---

# 📦 Components

| Component | Technology | Description | Port |
|---|---|---|---|
| RAN Simulator | FastAPI + Uvicorn | Simulates 5G gNodeBs and UE traffic | 8000 |
| RL xApp | Python + Stable-Baselines3 | PPO-based traffic optimization agent | 8001 |
| Prometheus | Prometheus | Metrics collection and scraping | 9090 |
| Grafana | Grafana | Real-time monitoring dashboard | 3000 |
| ConfigMap | Kubernetes | Dynamic runtime configuration | — |

---

# 📊 Metrics

The simulator exports Prometheus metrics including:

| Metric | Description |
|---|---|
| `ran_prb_utilization_percent` | PRB usage percentage |
| `ran_throughput_mbps` | Aggregate throughput |
| `ran_active_ues` | Number of active users |
| `ran_handover_count_total` | Total handovers executed |
| `rl_reward` | Current PPO reward |

---

# 🔄 Data Flow

1. RAN Simulator generates dynamic network conditions
2. RL xApp reads network metrics
3. PPO Agent decides whether handovers are required
4. Metrics are exported to Prometheus
5. Grafana visualizes the entire system in real time

---

# 🚀 Deployment Guide

## Prerequisites

```bash
docker --version
minikube version
kubectl version
```

Recommended:

- Docker Engine 20+
- Minikube v1.30+
- Kubernetes v1.24+

---

# 1️⃣ Start Minikube

```bash
minikube start --memory 6144 --cpus 4 --driver=docker
```

---

# 2️⃣ Build Docker Images

```bash
eval $(minikube -p minikube docker-env)

docker compose build
```

---

# 3️⃣ Deploy to Kubernetes

```bash
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/02-ran-simulator.yaml
kubectl apply -f k8s/03-rl-xapp.yaml
kubectl apply -f k8s/04-prometheus.yaml
kubectl apply -f k8s/05-grafana.yaml
```

---

# 4️⃣ Verify Deployment

```bash
kubectl get pods -w
```

Expected status:

```text
Running
```

for all services.

---

# 🌐 Access Services

## RAN Simulator API

```bash
kubectl port-forward svc/ran-simulator 8888:8000
```

Open:

```text
http://localhost:8888/docs
```

---

## Grafana Dashboard

```bash
kubectl port-forward svc/grafana 3000:3000
```

Open:

```text
http://localhost:3000
```

Default credentials:

```text
admin / admin
```

---

## Stream RL xApp Logs

```bash
kubectl logs -l app=rl-xapp -f
```

---

# 🧪 Chaos Engineering Tests

## Test 1 — Self-Healing

Delete the RAN Simulator pod:

```bash
kubectl delete pod -l app=ran-simulator
```

Kubernetes automatically recreates the pod.

---

## Test 2 — Traffic Spike Simulation

Edit the ConfigMap:

```bash
kubectl edit configmap network-config
```

Enable:

```yaml
UE_SPIKE_ENABLED: "true"
```

Expected behavior:

- PRB utilization spikes to 95–100%
- RL xApp triggers handovers
- Utilization stabilizes below 85%

---

# 📁 Project Structure

```text
smart-oran-xapp/
│
├── k8s/
│   ├── 01-configmap.yaml
│   ├── 02-ran-simulator.yaml
│   ├── 03-rl-xapp.yaml
│   ├── 04-prometheus.yaml
│   └── 05-grafana.yaml
│
├── services/
│   ├── ran-simulator/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── simulator.py
│   │
│   ├── rl-xapp/
│   │   ├── Dockerfile
│   │   ├── agent.py
│   │   └── trainer.py
│   │
│   └── prometheus/
│       └── prometheus.yml
│
├── docker-compose.yaml
└── README.md
```

---

# 🔧 Troubleshooting

| Problem | Solution |
|---|---|
| CrashLoopBackOff | Increase Minikube memory |
| RL xApp connection refused | Ensure RAN Simulator starts first |
| Grafana shows "No Data" | Verify Prometheus targets |
| High CPU usage | Reduce Minikube CPU allocation |

---

# 📈 Performance Results

| Scenario | PRB Utilization | Recovery Time | Handovers |
|---|---|---|---|
| Baseline (20 UEs) | 32% | — | 0 |
| Traffic Spike (500 UEs) | 98% → 82% | 45s | 47 |
| Pod Failure | N/A | 8s | 0 |

---

# ✅ Key Engineering Highlights

- Cloud-native O-RAN simulation
- PPO Reinforcement Learning integration
- Kubernetes production-style deployment
- Self-healing infrastructure
- Real-time observability stack
- Automated Grafana provisioning
- Dynamic traffic balancing
- Chaos engineering validation

---

# ❤️ Final Note

This project demonstrates how AI, Kubernetes, and O-RAN concepts can be combined to build intelligent next-generation telecom infrastructure systems.
