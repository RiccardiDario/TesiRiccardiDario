# Configurazioni da testare
#sig_list = ["ecdsa_p256", "mldsa44", "p256_mldsa44"]
#sig_list = ["ecdsa_p384", "mldsa65", "p384_mldsa65"]
#sig_list = ["ecdsa_p521", "mldsa87", "p521_mldsa87"]
import json, subprocess, time, re, os, random, csv, pandas as pd, matplotlib.pyplot as plt
from collections import defaultdict

sig_list = ["ecdsa_p256", "mldsa44", "p256_mldsa44"]
NUM_RUNS, TIMEOUT, SLEEP = 10, 300, 2
SERVER, SERVER_DONE = "nginx_pq", r"--- Informazioni RAM ---"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
docker_compose_path, SHARED_VOLUMED_PATH = os.path.join(BASE_DIR, "docker-compose.yml"), os.path.join(BASE_DIR, "shared_plan")
GRAPH_DIR, FILTERED_LOG_DIR = os.path.join(BASE_DIR, "report/graph"), os.path.join(BASE_DIR, "report/filtered_logs")
for d in (GRAPH_DIR, FILTERED_LOG_DIR, SHARED_VOLUMED_PATH): os.makedirs(d, exist_ok=True)
plan_path = os.path.join(SHARED_VOLUMED_PATH, "plan.json")

def run_subprocess(cmd, timeout=None):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
        stdout, stderr = proc.communicate(timeout=timeout)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        proc.terminate()
        try: proc.wait(timeout=2)
        except subprocess.TimeoutExpired: proc.kill()
        return -1, "", "⏱️ Timeout"

def check_logs(container, pattern):
    code, out, err = run_subprocess(["docker", "logs", "--tail", "100", container], timeout=5)
    return re.search(pattern, out) is not None if out else False

def update_sig(sig):
    with open(docker_compose_path, "r", encoding="utf-8") as f:
        content = re.sub(r"(SIGNATURE_ALGO=)[^\s\n]+", f"\\1{sig}", f.read())
    with open(docker_compose_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Signature: {sig}")

def run_single_test(i):
    print(f"\n🚀 Test {i}")
    code, _, err = run_subprocess(["docker", "compose", "up", "-d"], timeout=30)
    if code != 0:
        print(f"❌ Errore: {err}")
        return
    print("⌛ In attesa log...")
    start = time.time()
    while time.time() - start < TIMEOUT:
        if check_logs(SERVER, SERVER_DONE):
            print(f"✅ Completato.")
            break
        time.sleep(SLEEP)
    else:
        print(f"⚠️ Timeout dopo {TIMEOUT}s.")
    print("🛑 Arresto container...")
    run_subprocess(["docker", "compose", "down"], timeout=30)
    print("🧹 Cleanup volumi...")
    for v in ["server_certs"]:
        run_subprocess(["docker", "volume", "rm", "-f", v])
    if i < NUM_RUNS: time.sleep(SLEEP)

def get_kem_sig_from_monitor_file(filepath):
    try:
        df = pd.read_csv(filepath)
        return df["KEM"].dropna().iloc[0].strip(), df["Signature"].dropna().iloc[0].strip()
    except Exception as e:
        print(f"Errore durante l'estrazione di KEM/SIG dal file di monitoraggio {filepath}: {e}")
        return "Unknown", "Unknown"

def run_all_tests_randomized():
    plan = [(i, j) for i in range(len(sig_list)) for j in range(1, NUM_RUNS + 1)]
    random.shuffle(plan)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    print(f"📤 Piano test salvato in {plan_path}")
    last_sig = None
    for scenario_idx, replica in plan:
        sig = sig_list[scenario_idx]
        print(f"\n🔀 Scenario: {sig} | Replica: {replica}")
        if sig != last_sig: update_sig(sig); last_sig = sig
        run_single_test(replica)
    print("\n🎉 Tutti i test completati!")

def generate_server_performance_graphs():
    print("📈 Generazione grafici performance server per ogni coppia KEM/Signature...")
    grouped_files = defaultdict(list)
    for file in os.listdir(FILTERED_LOG_DIR):
        if file.startswith("monitor_nginx_filtered") and file.endswith(".csv"):
            path = os.path.join(FILTERED_LOG_DIR, file)
            kem, sig = get_kem_sig_from_monitor_file(path)
            if kem != "Unknown" and sig != "Unknown": grouped_files[(kem, sig)].append(path)

    for (kem, sig), files in grouped_files.items():
        if len(files) < NUM_RUNS: print(f"⏭️ Salto {kem} + {sig} (solo {len(files)} file)"); continue
        out_path = os.path.join(GRAPH_DIR, f"server_cpu_memory_usage_{kem}_{sig}.png".replace("/", "_"))
        if os.path.exists(out_path): print(f"📁 Già esistente: {out_path}, salto."); continue

        dfs = []
        for f in files[:NUM_RUNS]:
            try:
                df = pd.read_csv(f)
                df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%d/%b/%Y:%H:%M:%S.%f")
                dfs.append(df)
            except Exception as e:
                print(f"⚠️ Errore nel parsing di {f}: {e}")
        if len(dfs) < NUM_RUNS:
            print(f"⚠️ File validi insufficienti per {kem} + {sig}, salto."); continue

        min_range = min((df["Timestamp"].max() - df["Timestamp"].min()).total_seconds() for df in dfs)
        df_monitor_avg = pd.concat([df[df["Timestamp"] <= df["Timestamp"].min() + pd.Timedelta(seconds=min_range)]
            .assign(Index=(df["Timestamp"] - df["Timestamp"].min()).dt.total_seconds() // 0.1)
            .groupby("Index")[["CPU (%)", "Mem (%)"]].mean().reset_index()
            for df in dfs]).groupby("Index")[["CPU (%)", "Mem (%)"]].mean().reset_index()

        time_ms = df_monitor_avg["Index"] * 100
        fig, ax = plt.subplots(figsize=(14, 7))
        ax.plot(time_ms, df_monitor_avg["CPU (%)"], label="CPU Usage (%)", color="red", marker="o")
        ax.plot(time_ms, df_monitor_avg["Mem (%)"], label="Memory Usage (%)", color="blue", marker="o")
        ax.set(xlabel="Time (ms)", ylabel="Usage (%)",
               title=f"Server Resource Usage Over Time\nKEM: {kem} | Signature: {sig}")
        ax.legend(title=f"KEM: {kem} | Signature: {sig}", loc="upper left", bbox_to_anchor=(1, 1))
        ax.grid(True, linestyle="--", alpha=0.7)
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"✅ Grafico generato: {out_path}")
        
if __name__ == "__main__":
    run_all_tests_randomized()
    generate_server_performance_graphs()