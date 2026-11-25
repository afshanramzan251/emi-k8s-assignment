import pandas as pd
import matplotlib.pyplot as plt

# 1. Graph 1: Avg Response Time vs Request Rate
df = pd.read_csv("results/fixed_summary.csv")
plt.figure(figsize=(8, 5))
for rep in [1, 2, 3]:
    sub = df[df["replicas"] == rep]
    plt.plot(sub["request_rate"], sub["avg_response_time_ms"], marker="o", label=f"{rep} Replica(s)")
plt.title("Average Response Time vs Request Rate")
plt.xlabel("Request Rate (req/s)")
plt.ylabel("Average Response Time (ms)")
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend()
plt.tight_layout()
plt.savefig("results/graph1_response_time.png", dpi=200)
plt.close()

# 2. Graph 2: Per-Pod CPU Utilization (%) Over Time during 100 req/s @ 3 Replicas
p100 = pd.read_csv("results/pod_metrics_r3_rate100.csv")
web100 = p100[p100["pod_name"].str.startswith("emi-web")].copy()
web100["cpu_util_percent"] = pd.to_numeric(web100["cpu_util_percent"], errors="coerce")
web100["elapsed_sec"] = web100.groupby("pod_name").cumcount() * 15

plt.figure(figsize=(8, 5))
for pod, grp in web100.groupby("pod_name"):
    plt.plot(grp["elapsed_sec"], grp["cpu_util_percent"], marker="o", label=pod)
plt.title("Per-Pod CPU Utilization Over Time (3 Replicas @ 100 req/s)")
plt.xlabel("Elapsed Time (seconds)")
plt.ylabel("CPU Utilization (% of 100m request)")
plt.grid(True, linestyle="--", alpha=0.6)
plt.legend()
plt.tight_layout()
plt.savefig("results/graph2_cpu_memory.png", dpi=200)
plt.close()

# 3. Graph 3: Request Rate, Avg CPU Utilization & Replicas over 10 Mins (Shared Time Axis)
hdf = pd.read_csv("results/hpa_metrics.csv")
hdf["cpu_clean"] = pd.to_numeric(hdf["avg_cpu_util_percent"], errors="coerce").ffill().fillna(0)

fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(9, 7.5), sharex=True)

ax1.step(hdf["elapsed_sec"], hdf["request_rate"], where="post", color="tab:blue", linewidth=2, label="Workload Rate (req/s)")
ax1.set_ylabel("Req/s")
ax1.set_title("HPA Autoscaling: Request Rate, CPU Utilization & Replicas (10 Minutes)")
ax1.grid(True, linestyle="--", alpha=0.6)
ax1.legend(loc="upper right")

ax2.plot(hdf["elapsed_sec"], hdf["cpu_clean"], color="tab:red", marker=".", label="Avg CPU Utilization (%)")
ax2.axhline(50, color="gray", linestyle="--", label="Target Threshold (50%)")
ax2.set_ylabel("CPU (%)")
ax2.grid(True, linestyle="--", alpha=0.6)
ax2.legend(loc="upper right")

ax3.step(hdf["elapsed_sec"], hdf["replicas"], where="post", color="tab:purple", linewidth=2, label="Active Replicas")
ax3.set_xlabel("Elapsed Time (seconds)")
ax3.set_ylabel("Replicas")
ax3.set_yticks([1, 2, 3, 4, 5])
ax3.grid(True, linestyle="--", alpha=0.6)
ax3.legend(loc="upper right")

fig.tight_layout()
plt.savefig("results/graph3_hpa_timeline.png", dpi=200)
plt.close()
print("Updated Graph 2 and Graph 3 successfully!")
