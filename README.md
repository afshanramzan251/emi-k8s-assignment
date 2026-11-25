# Loan EMI Calculator on Kubernetes (Minikube)
Course: DS-584 Cloud Computing (Fall 2026)
Student: Afshan Ramzan (MSDSF25M021)
Instructor: Dr. Muhammad Abdullah

## Repository Structure
- app/: Python REST API, web frontend, Dockerfile, and .dockerignore
- k8s/: Kubernetes YAML manifests (00-namespace.yaml to 06-hpa.yaml)
- scripts/: Load testing, HPA autoscaling test, and plotting scripts
- results/: Raw ApacheBench outputs, CPU/memory metrics CSVs, and graphs

## How to Run on a Fresh Minikube Cluster
1. minikube start
2. minikube addons enable ingress
3. minikube addons enable metrics-server
4. docker build -t emi-web:1.0 ./app
5. minikube image load emi-web:1.0
6. kubectl apply -f k8s/
7. Run minikube tunnel and map 127.0.0.1 emi.local in your hosts file, then open http://emi.local
