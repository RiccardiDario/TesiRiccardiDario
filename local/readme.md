# Guida all'Esecuzione del Progetto

## Avvio del Progetto

Per avviare l’intero progetto, eseguire:

```bash
docker compose up -d
```

⚠️ **Nota:**  
Nel caso in cui le immagini Docker non siano già presenti nel sistema o siano state modificate, `docker compose` procederà automaticamente alla loro **build**.  
Questa operazione può richiedere **diversi minuti** e comportare un uso intensivo delle risorse hardware.

Per garantire un'esecuzione pulita, si consiglia la seguente procedura:

1. Avviare il progetto con `docker compose up -d` (la build verrà eseguita se necessaria).
2. Una volta completata la build, arrestare i container:

    ```bash
    docker compose down
    ```

3. Riavviare i container per avviare l'ambiente in modo pulito e stabile:

    ```bash
    docker compose up -d
    ```

## Configurazione degli Algoritmi

Gli algoritmi **KEM** e di **firma** possono essere configurati nella sezione dedicata del file `docker-compose.yml`.

## Esecuzione di una Richiesta HTTPS nel Container

È possibile effettuare richieste HTTPS dall’interno del container Docker utilizzando **cURL** o **PycURL**.

### Utilizzo di cURL

```bash
curl --tlsv1.3 --cacert /opt/certs/CA.crt -v https://192.168.1.100
```

### Utilizzo di PycURL

```bash
python3 -c "import pycurl; from io import BytesIO; b = BytesIO(); c = pycurl.Curl(); \
c.setopt(c.URL, 'https://192.168.1.100'); c.setopt(c.CAINFO, '/opt/certs/CA.crt'); \
c.setopt(c.SSLVERSION, c.SSLVERSION_TLSv1_3); c.setopt(c.VERBOSE, True); \
c.setopt(c.WRITEDATA, b); c.perform(); print('HTTP Response Code:', c.getinfo(c.RESPONSE_CODE)); \
print('Response body:\\n', b.getvalue().decode()); c.close()"
```

## Terminare l’Esecuzione

Per interrompere l’esecuzione e rimuovere i container:

```bash
docker compose down
```

## Esecuzione dei Test Automatici

Per eseguire i test automatici, è necessario Python con i seguenti pacchetti:

- `psutil`
- `matplotlib`
- `pandas`
- `numpy`

### Ambiente Virtuale su Windows

Se l’host utilizza **Windows**, è possibile creare un ambiente virtuale con i pacchetti richiesti tramite lo script:

```powershell
setup_env.ps1
```

### Avvio dei Test

Eseguire i test con il comando:

```bash
python run_test.py
```
