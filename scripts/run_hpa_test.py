import csv, json, os, random, subprocess, threading, time
from datetime import datetime

AB_PATH = r"C:\Users\hp\AppData\Local\Microsoft\WinGet\Packages\ApacheLounge.httpd_Microsoft.Winget.Source_8wekyb3d8bbwe\Apache24\bin\ab.exe"
URL = "http://127.0.0.1:8080/api/emi"

# 2m @ 10 req/s, 5m @ 100 req/s, 3m @ 10 req/s (Total 10 mins)
PHASES = [(120, 10), (300, 100), (180, 10)]
current_rate = 10

def run_cmd(cmd):
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout, res.stderr

def hpa_monitor(stop_event, start_time):
    rows = []
    raw_lines = []
    while not stop_event.is_set():
        elapsed = round(time.time() - start_time, 1)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        out_txt, _ = run_cmd(["kubectl", "get", "hpa", "emi-web", "-n", "emi"])
        out_json, _ = run_cmd(["kubectl", "get", "hpa", "emi-web", "-n", "emi", "-o", "json"])
        raw_lines.append(f"[{ts} | t={elapsed}s]\n{out_txt}")

        cpu_util = ""
        replicas = 1
        try:
            data = json.loads(out_json)
            replicas = data["status"].get("currentReplicas", 1)
            cur_metrics = data["status"].get("currentMetrics", [])
            if cur_metrics:
                cpu_util = cur_metrics[0]["resource"]["current"].get("averageUtilization", "")
        except Exception:
            pass

        print(f"[t={elapsed:5.1f}s] Rate={current_rate:3d} req/s | CPU={str(cpu_util):>3}% | Replicas={replicas}")
        rows.append([ts, elapsed, current_rate, cpu_util, replicas])
        time.sleep(15)

    with open("results/hpa_metrics.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "elapsed_sec", "request_rate", "avg_cpu_util_percent", "replicas"])
        w.writerows(rows)

    with open("results/hpa_raw_output.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(raw_lines))

print("Applying HPA and resetting emi-web to 1 replica...")
run_cmd(["kubectl", "scale", "deployment", "emi-web", "--replicas=1", "-n", "emi"])
run_cmd(["kubectl", "apply", "-f", "k8s/06-hpa.yaml"])
time.sleep(20)

start_t = time.time()
stop_ev = threading.Event()
mon = threading.Thread(target=hpa_monitor, args=(stop_ev, start_t))
mon.start()

payload_file = "results/tmp_hpa_payload.json"
for dur, rate in PHASES:
    current_rate = rate
    print(f"\n>>> Starting phase: {rate} req/s for {dur}s <<<")
    phase_start = time.time()
    for sec in range(dur):
        target_t = phase_start + sec
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
        subprocess.Popen(
            [AB_PATH, "-n", str(rate), "-c", str(conc), "-p", payload_file, "-T", "application/json", "-H", "Host: emi.local", URL],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )

stop_ev.set()
mon.join()
print("\n10-minute HPA test complete! Saved to results/hpa_metrics.csv")