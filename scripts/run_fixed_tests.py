import csv, json, os, random, re, subprocess, threading, time
from datetime import datetime
import psutil

AB_PATH = r"C:\Users\hp\AppData\Local\Microsoft\WinGet\Packages\ApacheLounge.httpd_Microsoft.Winget.Source_8wekyb3d8bbwe\Apache24\bin\ab.exe"
URL = "http://127.0.0.1:8080/api/emi"
REPLICAS_LIST = [1, 2, 3]
RATES_LIST = [10, 25, 50, 100, 200]
DURATION = 60

os.makedirs("results", exist_ok=True)

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout, res.stderr

def profile_worker(stop_event, pod_csv, host_csv):
    pod_rows = []
    host_rows = []
    last_pod_poll = 0.0
    while not stop_event.is_set():
        now = time.time()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cpu_pct = psutil.cpu_percent(interval=1.0)
        host_rows.append([ts, cpu_pct])
        if now - last_pod_poll >= 15.0:
            last_pod_poll = now
            out, _ = run_cmd(["kubectl", "top", "pods", "-n", "emi", "--no-headers"])
            for line in out.strip().splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    pod, cpu_s, mem_s = parts[0], parts[1], parts[2]
                    cpu_m = int(cpu_s.replace("m", "")) if cpu_s.endswith("m") else int(float(cpu_s) * 1000)
                    mem_mi = int(mem_s.replace("Mi", "")) if mem_s.endswith("Mi") else 0
                    util_pct = round((cpu_m / 100.0) * 100.0, 1) if pod.startswith("emi-web") else ""
                    pod_rows.append([ts, pod, cpu_m, util_pct, mem_mi])

    with open(host_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "host_cpu_percent"])
        w.writerows(host_rows)

    with open(pod_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "pod_name", "cpu_millicores", "cpu_util_percent", "memory_mi"])
        w.writerows(pod_rows)

def send_paced_ab(rate, duration, raw_log_path):
    payload_file = "results/tmp_payload.json"
    procs = []
    start = time.time()
    for sec in range(duration):
        target_t = start + sec
        if time.time() < target_t:
            time.sleep(target_t - time.time())
        body = {
            "principal": random.randint(50000, 1000000),
            "rate": round(random.uniform(5.0, 18.0), 2),
            "months": random.randint(12, 120),
        }
        with open(payload_file, "w") as f:
            json.dump(body, f)
        conc = min(rate, 25)
        cmd = [
            AB_PATH, "-n", str(rate), "-c", str(conc),
            "-p", payload_file, "-T", "application/json",
            "-H", "Host: emi.local", URL
        ]
        procs.append(subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))

    total_reqs = 0
    weighted_time_ms = 0.0
    total_errors = 0
    raw_chunks = []

    for p in procs:
        out, err = p.communicate()
        raw_chunks.append(out + err)
        m_comp = re.search(r"Complete requests:\s+(\d+)", out)
        m_fail = re.search(r"Failed requests:\s+(\d+)", out)
        m_non2xx = re.search(r"Non-2xx responses:\s+(\d+)", out)
        m_tpr = re.search(r"Time per request:\s+([\d.]+)\s+\[ms\]\s+\(mean\)", out)

        comp = int(m_comp.group(1)) if m_comp else 0
        fail = int(m_fail.group(1)) if m_fail else 0
        non2xx = int(m_non2xx.group(1)) if m_non2xx else 0
        tpr = float(m_tpr.group(1)) if m_tpr else 0.0

        ok = max(comp - fail, 0)
        total_reqs += ok
        weighted_time_ms += tpr * ok
        total_errors += (fail + non2xx)

    with open(raw_log_path, "w", encoding="utf-8") as f:
        f.write("\n--- BATCH ---\n".join(raw_chunks))

    avg_rt = round(weighted_time_ms / total_reqs, 2) if total_reqs > 0 else 0.0
    return avg_rt, total_errors

summary_rows = []
for rep in REPLICAS_LIST:
    print(f"\n=== Scaling emi-web to {rep} replica(s) ===")
    run_cmd(["kubectl", "scale", "deployment", "emi-web", f"--replicas={rep}", "-n", "emi"])
    run_cmd(["kubectl", "rollout", "status", "deployment/emi-web", "-n", "emi"])
    time.sleep(10)

    for rate in RATES_LIST:
        print(f"Running {rep} replica(s) @ {rate} req/s for {DURATION}s...")
        stop_ev = threading.Event()
        pod_csv = f"results/pod_metrics_r{rep}_rate{rate}.csv"
        host_csv = f"results/host_cpu_r{rep}_rate{rate}.csv"
        raw_log = f"results/ab_raw_r{rep}_rate{rate}.txt"

        t = threading.Thread(target=profile_worker, args=(stop_ev, pod_csv, host_csv))
        t.start()
        avg_rt, errors = send_paced_ab(rate, DURATION, raw_log)
        stop_ev.set()
        t.join()

        print(f"  -> Avg Response Time: {avg_rt} ms | Errors: {errors}")
        summary_rows.append([rep, rate, avg_rt, errors])
        time.sleep(5)

with open("results/fixed_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["replicas", "request_rate", "avg_response_time_ms", "error_count"])
    w.writerows(summary_rows)

print("\nAll 15 fixed-replica runs complete! Saved to results/fixed_summary.csv")