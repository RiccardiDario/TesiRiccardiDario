import subprocess, re, psutil, csv, time, os, pandas as pd
from datetime import datetime

def get_next_filename(path, name, ext, counter=1):
    while os.path.exists(f"{path}/{name}{counter}.{ext}"): counter += 1
    return f"{path}/{name}{counter}.{ext}"

RESOURCE_LOG_DIR, FILTERED_LOG_DIR = "/opt/nginx/output/resource_logs", "/opt/nginx/output/filtered_logs"
for d in (RESOURCE_LOG_DIR, FILTERED_LOG_DIR): os.makedirs(d, exist_ok=True)

RESOURCE_LOG, OUTPUT_FILE = get_next_filename(RESOURCE_LOG_DIR, "monitor_nginx", "csv"), get_next_filename(FILTERED_LOG_DIR, "monitor_nginx_filtered", "csv")
ACCESS_LOG, AVG_METRICS_FILE = "/opt/nginx/logs/access_custom.log",f"{FILTERED_LOG_DIR}/avg_nginx_usage.csv"
EXPECTED_REQUESTS, SAMPLING_INTERVAL = 500, 0.1

def get_kem_sig_from_logs(log_path, cert_path):
    kem_map = { "0x0200": "mlkem512", "0x0201": "mlkem768", "0x0202": "mlkem1024", "0x2f4b": "p256_mlkem512", "0x2f4c": "p384_mlkem768", "0x2f4d": "p521_mlkem1024" }
    sig_oid_map = { "2.16.840.1.101.3.4.3.17": "mldsa44", "2.16.840.1.101.3.4.3.18": "mldsa65", "2.16.840.1.101.3.4.3.19": "mldsa87",
        "1.3.9999.7.5": "p256_mldsa44", "1.3.9999.7.7": "p384_mldsa65", "1.3.9999.7.8": "p521_mldsa87"}
    kem, sig_alg = "Unknown", "Unknown"
    try:
        with open(log_path, "r") as f:
            for line in reversed(f.readlines()):
                if m := re.search(r'KEM=([\w\d._:-]+)', line):
                    kem = kem_map.get(m.group(1), m.group(1)); break
    except Exception as e:
        print(f"Errore log Nginx: {e}")

    try:
        result = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-text"], capture_output=True, text=True, check=True)
        for line in result.stdout.splitlines():
            if "Signature Algorithm" in line:
                oid = line.strip().split()[-1]
                sig_alg = oid if oid.isalnum() else sig_oid_map.get(oid, oid)
                break
    except Exception as e:
        print(f"Errore firma certificato: {e}")
    return kem, sig_alg

def append_kem_sig_to_csv(f, kem, sig):
    try:
        df = pd.read_csv(f)
        df["KEM"] = df.get("KEM", ""); df["Signature"] = df.get("Signature", "")
        if "avg_nginx_usage" in f: df.loc[df.index[-1], ["KEM", "Signature"]] = kem, sig
        else: df[["KEM", "Signature"]] = kem, sig
        df.to_csv(f, index=False)
    except Exception as e:
        print(f"❌ Errore su {f}: {e}")

def monitor_resources():
    print("Inizio monitoraggio delle risorse...")
    with open(RESOURCE_LOG, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        psutil.cpu_percent(None)
        w.writerow(["Timestamp", "CPU (%)", "Mem (%)", "Bytes Sent", "Bytes Recv", "Conn Attive"])
        while True:
            if os.path.exists(ACCESS_LOG) and sum(1 for _ in open(ACCESS_LOG, encoding="utf-8")) >= EXPECTED_REQUESTS:
                break
            w.writerow([datetime.now().strftime("%d/%b/%Y:%H:%M:%S.%f")[:-3], psutil.cpu_percent(), psutil.virtual_memory().percent,
                        *psutil.net_io_counters()[:2], sum(1 for c in psutil.net_connections("inet") if c.status == "ESTABLISHED")])
            f.flush()
            time.sleep(SAMPLING_INTERVAL)
    print("Monitoraggio terminato.")

def analyze_logs():
    if not os.path.exists(ACCESS_LOG): return None, None
    try:
        with open(ACCESS_LOG, encoding="utf-8") as f:
            timestamps = [datetime.fromtimestamp(float(l.split()[3][1:-1])) for l in f if len(l.split()) >= 4]
        return (min(timestamps), max(timestamps)) if timestamps else (None, None)
    except: return None, None

def analyze_performance():
    s, e = analyze_logs()
    if not s or not e: return print("ERRORE: Intervallo di test non disponibile.")
    try:
        with open(RESOURCE_LOG, encoding="utf-8") as f:
            data = [r for r in csv.DictReader(f) if s <= datetime.strptime(r["Timestamp"], "%d/%b/%Y:%H:%M:%S.%f") <= e]
        if not data: return print("ERRORE: Nessun dato nel periodo di test.")
        with open(OUTPUT_FILE, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Timestamp", "CPU (%)", "Mem (%)", "Bytes Sent", "Bytes Recv", "Conn Attive"])
            w.writerows([[r[c] for c in ["Timestamp", "CPU (%)", "Mem (%)", "Bytes Sent", "Bytes Recv", "Conn Attive"]] for r in data])
        print(f"Salvati {len(data)} campionamenti in {OUTPUT_FILE}.")
    except Exception as e:
        print(f"ERRORE nel salvataggio dati: {e}")

def generate_avg_resource_usage():
    try:
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            data = list(csv.DictReader(f))
        if not data: return print("ERRORE: Nessun dato disponibile per calcolare la media.")
        avg_cpu = sum(float(r["CPU (%)"]) for r in data) / len(data)
        avg_ram = sum(float(r["Mem (%)"]) for r in data) / len(data)
        file_exists = os.path.isfile(AVG_METRICS_FILE)
        with open(AVG_METRICS_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if not file_exists: w.writerow(["Timestamp", "CPU Media (%)", "Mem Media (%)"])
            w.writerow([datetime.now().strftime("%d/%b/%Y:%H:%M:%S"), f"{avg_cpu:.2f}", f"{avg_ram:.2f}"])
        print(f"Medie CPU e RAM aggiornate in {AVG_METRICS_FILE}.")
    except Exception as e:
        print(f"ERRORE nel calcolo delle medie: {e}")
    
def log_system_info():
    cpu_info = psutil.cpu_freq()
    ram_info = psutil.virtual_memory()
    print(f"--- Informazioni CPU ---")
    print(f"Core logici disponibili: {psutil.cpu_count(logical=True)}")
    print(f"Core fisici disponibili: {psutil.cpu_count(logical=False)}")
    print(f"\n--- Informazioni RAM ---")
    print(f"RAM totale: {ram_info.total / (1024**3):.2f} GB")

if __name__ == "__main__":
    try:
        monitor_resources()
        analyze_performance()
        generate_avg_resource_usage()
        kem, sig = get_kem_sig_from_logs(ACCESS_LOG, "/etc/nginx/certs/qsc-ca-chain.crt")
        for f in [RESOURCE_LOG, OUTPUT_FILE, AVG_METRICS_FILE]: append_kem_sig_to_csv(f, kem, sig)
        log_system_info()
    except Exception as e:
        print(f"ERRORE GENERALE: {e}")