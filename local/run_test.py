# Configurazioni da testare
#sig_list, kem_list = ["ecdsa_p256", "mldsa44", "p256_mldsa44"], ["secp256r1", "mlkem512", "p256_mlkem512"]
#sig_list, kem_list= ["ecdsa_p384", "mldsa65", "p384_mldsa65"], ["secp384r1", "mlkem768", "p384_mlkem768"]
#sig_list, kem_list = ["ecdsa_p521", "mldsa87", "p521_mldsa87"], ["secp521r1", "mlkem1024","p521_mlkem1024"]
import json, subprocess, psutil, time, math, re, logging, os, random, csv, pandas as pd, numpy as np, matplotlib.pyplot as plt
from collections import defaultdict

sig_list, kem_list = ["ecdsa_p256", "mldsa44", "p256_mldsa44"], ["secp256r1", "mlkem512", "p256_mlkem512"]
NUM_RUNS, TIMEOUT, SLEEP = 10, 300, 2
CLIENT, SERVER = "client_analysis", "nginx_pq"
CLIENT_DONE, SERVER_DONE = r"\[INFO\] Test completato in .* Report: /app/output/request_logs/request_client\d+\.csv", r"--- Informazioni RAM ---"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
docker_compose_path, SHARED_VOLUMED_PATH = os.path.join(BASE_DIR, "docker-compose.yml"), os.path.join(BASE_DIR, "shared_plan")
output_csv = os.path.join(BASE_DIR, "report/request_logs/avg/average_metrics_per_request.csv")
output_csv_avg = os.path.join(BASE_DIR, "report/request_logs/avg/average_metrics.csv")
GRAPH_DIR, FILTERED_LOG_DIR = os.path.join(BASE_DIR, "report/graph"), os.path.join(BASE_DIR, "report/filtered_logs")
input_folder, monitor_folder = os.path.join(BASE_DIR, "report/request_logs"), os.path.join(BASE_DIR, "report/system_logs")
for d in (GRAPH_DIR, FILTERED_LOG_DIR, input_folder, monitor_folder, SHARED_VOLUMED_PATH): os.makedirs(d, exist_ok=True)
plan_path = os.path.join(SHARED_VOLUMED_PATH, "plan.json")

def get_kem_sig_from_file(filepath):
    try:
        df = pd.read_csv(filepath)
        df = df[df["Status"] == "Success"]
        return df["KEM"].dropna().mode()[0].strip(), df["Signature"].dropna().mode()[0].strip()
    except Exception as e:
        print(f"Errore durante l'estrazione di KEM/SIG da {filepath}: {e}")
        return "Unknown", "Unknown"

def group_request_files_by_kem_sig(folder):
    grouped = defaultdict(list)
    for file in sorted(f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))):
        if file.startswith("request_client") and file.endswith(".csv"):
            path = os.path.join(folder, file)
            kem, sig = get_kem_sig_from_file(path)
            if kem != "Unknown" and sig != "Unknown": grouped[(kem, sig)].append(path)
    return {k: v for k, v in grouped.items() if len(v) >= NUM_RUNS}

def generate_average_metrics_per_request(kem, sig, files, output_csv):
    dfs = [pd.read_csv(f).sort_values("Request_Number").reset_index(drop=True) for f in files[:NUM_RUNS]]
    metric_cols = ["Connect_Time(ms)", "TLS_Handshake(ms)", "Total_Time(ms)", "Elapsed_Time(ms)", "Cert_Size(B)"]
    result_rows = []
    for i in range(len(dfs[0])):
        avg_row = sum(df.loc[i, metric_cols].values for df in dfs) / len(dfs)
        result_rows.append([kem, sig] + [round(val, 3) for val in avg_row.tolist()])

    file_exists = os.path.exists(output_csv)
    with open(output_csv, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["KEM", "Signature", "Avg_Connect_Time(ms)", "Avg_Handshake_Time(ms)",
                             "Avg_Total_Time(ms)", "Avg_Elapsed_Time(ms)", "Avg_Cert_Size(B)"])
        writer.writerows(result_rows)
    print(f"✅ Aggiunte {len(result_rows)} righe ad average_metrics_per_request.csv per {kem} - {sig}")

def process_all_batches_for_avg_per_request(input_folder, output_csv):
    grouped_files = group_request_files_by_kem_sig(input_folder)
    for (kem, sig), file_list in grouped_files.items():
        generate_average_metrics_per_request(kem, sig, file_list, output_csv)

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

def update_kem(kem):
    with open(docker_compose_path, "r", encoding="utf-8") as f:
        content = re.sub(r"(DEFAULT_GROUPS=)[^\s\n]+", f"\\1{kem}", f.read())
    with open(docker_compose_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ KEM: {kem}")

def update_sig(sig):
    with open(docker_compose_path, "r", encoding="utf-8") as f:
        content = re.sub(r"(SIGNATURE_ALGO=)[^\s\n]+", f"\\1{sig}", f.read())
    with open(docker_compose_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✅ Signature: {sig}")

def run_single_test(i):
    print(f"\n🚀 Test {i}")
    code, _, err = run_subprocess(["docker-compose", "up", "-d"], timeout=30)
    if code != 0:
        print(f"❌ Errore: {err}")
        return
    print("⌛ In attesa log...")
    start = time.time()
    while time.time() - start < TIMEOUT:
        if check_logs(CLIENT, CLIENT_DONE) and check_logs(SERVER, SERVER_DONE):
            print(f"✅ Completato.")
            break
        time.sleep(SLEEP)
    else:
        print(f"⚠️ Timeout dopo {TIMEOUT}s.")
    print("🛑 Arresto container...")
    run_subprocess(["docker-compose", "down"], timeout=30)
    print("🧹 Cleanup volumi...")
    for v in ["local_certs", "local_pcap", "local_tls_keys"]:
        run_subprocess(["docker", "volume", "rm", "-f", v])
    if i < NUM_RUNS: time.sleep(SLEEP)

def generate_graphs_from_average_per_request():
    if not os.path.exists(output_csv): logging.warning("File average_metrics_per_request.csv non trovato."); return
    df = pd.read_csv(output_csv)
    if df.empty:  logging.warning("Il file delle medie per richiesta è vuoto."); return

    reqs_per_batch, reqs_per_plot, total_batches = 500, 100, len(df) // 500
    metrics = ["Avg_Connect_Time(ms)", "Avg_Handshake_Time(ms)", "Avg_Total_Time(ms)", "Avg_Elapsed_Time(ms)"]
    batch_labels, boxplot_data = [], {k: [] for k in metrics}

    for b in range(total_batches):
        df_batch = df.iloc[b * reqs_per_batch:(b + 1) * reqs_per_batch]
        kem, sig = df_batch["KEM"].iloc[0], df_batch["Signature"].iloc[0]
        cert_size = int(df_batch["Avg_Cert_Size(B)"].iloc[0])
        batch_labels.append(f"{kem}\n{sig}\n{cert_size} B")
        for m in metrics: boxplot_data[m].append(df_batch[m].tolist())

        for i in range(0, reqs_per_batch, reqs_per_plot):
            df_subset = df_batch.iloc[i:i + reqs_per_plot].reset_index(drop=True)
            x = list(range(i + 1, i + 1 + len(df_subset)))
            cert_str = f"{cert_size:.2f} B"

            # Elapsed Time
            plt.figure(figsize=(10, 5))
            plt.plot(x, df_subset["Avg_Elapsed_Time(ms)"], marker='o', linestyle='-', color='blue', label="Elapsed Time (ms)")
            plt.xlabel("Request Completion Order"); plt.ylabel("Elapsed Time (ms)")
            plt.title(f"Elapsed Time per Request\nKEM: {kem} | Signature: {sig}")
            plt.legend(title=f"Certificate Size: {cert_str}"); plt.grid(True); plt.tight_layout()
            plt.savefig(os.path.join(GRAPH_DIR, f"elapsed_time_graph_batch_{b+1}_{x[0]}_{x[-1]}.png")); plt.close()

            # TLS Breakdown
            connect = df_subset["Avg_Connect_Time(ms)"]
            handshake = df_subset["Avg_Handshake_Time(ms)"] - connect
            total = df_subset["Avg_Total_Time(ms)"] - df_subset["Avg_Handshake_Time(ms)"]
            plt.figure(figsize=(14, 7))
            plt.bar(x, connect, label="Connect Time", color="red", alpha=0.7)
            plt.bar(x, handshake, bottom=connect, label="TLS Handshake Time", color="orange", alpha=0.7)
            plt.bar(x, total, bottom=df_subset["Avg_Handshake_Time(ms)"], label="Total Time", color="gray", alpha=0.7)
            plt.xlabel("Request Completion Order"); plt.ylabel("Time (ms)")
            plt.title(f"Timing Breakdown for TLS Connections\nKEM: {kem} | Signature: {sig}")
            plt.legend(title=f"Certificate Size: {cert_str}"); plt.grid(axis="y", linestyle="--", alpha=0.7)
            plt.tight_layout(); plt.savefig(os.path.join(GRAPH_DIR, f"tls_avg_graph_batch_{b+1}_{x[0]}_{x[-1]}.png"), dpi=300); plt.close()

    # Boxplot ogni 3 batch
    max_per_image, whis_val, perc_limit = 3, 4.0, 99
    for metric, ylabel in {
        "Avg_Connect_Time(ms)": "Connect Time (ms)",
        "Avg_Handshake_Time(ms)": "Handshake Time (ms)",
        "Avg_Total_Time(ms)": "Total Time (ms)",
        "Avg_Elapsed_Time(ms)": "Elapsed Time (ms)"
    }.items():
        for img_index in range(math.ceil(len(batch_labels) / max_per_image)):
            start, end = img_index * max_per_image, (img_index + 1) * max_per_image
            data_subset, labels_subset = boxplot_data[metric][start:end], batch_labels[start:end]

            fig = plt.figure(figsize=(max(6, len(labels_subset) * 1.8), 6))
            ax = fig.add_axes([0.1, 0.15, 0.8, 0.75])
            bp = ax.boxplot(data_subset, patch_artist=True, whis=whis_val,
                            boxprops=dict(facecolor='lightblue', alpha=0.7, edgecolor='black', linewidth=1.5),
                            whiskerprops=dict(color='black', linewidth=2),
                            capprops=dict(color='black', linewidth=2),
                            medianprops=dict(color='red', linewidth=2),
                            flierprops=dict(marker='o', color='black', markersize=6, alpha=0.6))

            flat_data = [v for batch in data_subset for v in batch]
            if flat_data:
                perc_y = np.percentile(flat_data, perc_limit)
                box_stats = [np.percentile(b, 75) + whis_val * (np.percentile(b, 75) - np.percentile(b, 25)) for b in data_subset]
                y_max = max(perc_y, max(box_stats)); y_min = min(min(b) for b in data_subset)
                y_margin = (y_max - y_min) * 0.2
                ax.set_ylim(max(0, y_min - y_margin), y_max + y_margin)

                for idx, box in enumerate(data_subset):
                    outliers = sum(v > np.percentile(box, perc_limit) for v in box)
                    if outliers > 0:
                        ax.annotate(f"+{outliers} outlier", xy=(idx + 1, y_max + y_margin * 0.1),
                                    ha='center', fontsize=8, color='gray')

            ax.set_title(ylabel); ax.set_ylabel(ylabel)
            ax.set_xticks(range(1, len(labels_subset) + 1))
            ax.set_xticklabels(labels_subset, rotation=30, ha="right")
            ax.set_xlim(0.5, len(labels_subset) + 0.5)
            plt.savefig(os.path.join(GRAPH_DIR, f"{ylabel.replace(' ', '_')}_boxplot_part{img_index + 1}.png"), dpi=300)
            plt.close(fig)

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

def get_kem_sig_from_monitor_file(filepath):
    try:
        df = pd.read_csv(filepath)
        return df["KEM"].dropna().iloc[0].strip(), df["Signature"].dropna().iloc[0].strip()
    except Exception as e:
        print(f"Errore durante l'estrazione di KEM/SIG dal file di monitoraggio {filepath}: {e}")
        return "Unknown", "Unknown"

def generate_system_monitor_graph():
    folder = os.path.join(BASE_DIR, "report", "system_logs")
    files = [os.path.join(folder, f) for f in os.listdir(folder) if f.startswith("system_client") and f.endswith(".csv")]
    if not files: print("⚠️ Nessun file di monitoraggio trovato."); return

    grouped = defaultdict(list)
    for path in files:
        try:
            df = pd.read_csv(path)
            kem, sig = df["KEM"].dropna().iloc[0], df["Signature"].dropna().iloc[0]
            grouped[(kem, sig)].append(df)
        except Exception as e: print(f"Errore durante la lettura di {path}: {e}")

    for (kem, sig), dfs in grouped.items():
        if len(dfs) < NUM_RUNS:
            print(f"⏭️ Non abbastanza file per {kem} + {sig} (trovati {len(dfs)})"); continue

        for df in dfs:
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        min_range = min((df["Timestamp"].max() - df["Timestamp"].min()).total_seconds() for df in dfs)

        df_avg = pd.concat([df[df["Timestamp"] <= df["Timestamp"].min() + pd.Timedelta(seconds=min_range)]
            .assign(Index=lambda x: (x["Timestamp"] - x["Timestamp"].min()).dt.total_seconds() // 0.1)
            .groupby("Index")[["CPU_Usage(%)", "Memory_Usage(%)"]].mean().reset_index()
            for df in dfs]).groupby("Index")[["CPU_Usage(%)", "Memory_Usage(%)"]].mean().reset_index()

        x = (df_avg["Index"] * 100).tolist()
        mem_total = psutil.virtual_memory().total / (1024 ** 2)
        cores = psutil.cpu_count(logical=True)
        plt.figure(figsize=(14, 6))
        plt.plot(x, df_avg["CPU_Usage(%)"], label="CPU Usage (%)", color="green", marker="o")
        plt.plot(x, df_avg["Memory_Usage(%)"], label="Memory Usage (%)", color="purple", marker="x")
        plt.xlabel("Time (ms)"); plt.ylabel("Usage (%)")
        plt.title(f"CPU & RAM Usage Over Time\nKEM: {kem} | Signature: {sig}")
        plt.legend(title=f"Cores: {cores} | RAM: {mem_total:.1f} MB", loc="upper right")
        plt.grid(True, linestyle="--", alpha=0.6); plt.tight_layout()
        fname = f"resource_usage_{kem}_{sig}".replace("/", "_").replace("\n", "_").strip() + ".png"
        plt.savefig(os.path.join(GRAPH_DIR, fname), dpi=300); plt.close()
        print(f"✅ Grafico salvato: {fname}")

def run_all_tests_randomized():
    plan = [(i, j) for i in range(len(kem_list)) for j in range(1, NUM_RUNS + 1)]
    random.shuffle(plan)
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f)
    print(f"📤 Piano test salvato in {plan_path}")
    last_kem, last_sig = None, None
    for scenario_idx, replica in plan:
        kem, sig = kem_list[scenario_idx], sig_list[scenario_idx]
        print(f"\n🔀 Scenario: {kem} + {sig} | Replica: {replica}")
        if kem != last_kem: update_kem(kem); last_kem = kem
        if sig != last_sig: update_sig(sig); last_sig = sig
        run_single_test(replica)
    print("\n🎉 Tutti i test completati!")

def classify_algorithms_and_update_csv(csv_path):
    if not os.path.exists(csv_path): return
    df = pd.read_csv(csv_path)
    df["Algorithms"] = df.apply(lambda r: (
        "Ibrido" if "_" in r["KEM"].strip() or "_" in r["Signature"].strip() else
        "Post-Quantum" if r["KEM"].strip() in {"mlkem512","mlkem768","mlkem1024"} and 
                          r["Signature"].strip() in {"mldsa44","mldsa65","mldsa87"} else
        "Pre-Quantum" if r["KEM"].strip() in {"secp256r1","secp384r1","secp521r1"} and 
                          r["Signature"].strip() in {"ecdsa-with-SHA256","ecdsa-with-SHA384","ecdsa-with-SHA512"} else
        "Sconosciuto"), axis=1)
    df.to_csv(csv_path, index=False)
    print(f"✅ Aggiunta colonna 'algorithms' a {csv_path}")

if __name__ == "__main__":
    run_all_tests_randomized()
    print(f"\n📊 Generazione medie e grafici per tutti i batch completati...")
    process_all_batches_for_avg_per_request(input_folder, output_csv)
    classify_algorithms_and_update_csv(output_csv_avg)
    generate_graphs_from_average_per_request()
    generate_system_monitor_graph()
    generate_server_performance_graphs()  