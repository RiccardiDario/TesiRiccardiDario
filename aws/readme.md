## Configurazione ed Esecuzione con Ansible

### 1. Preparazione 

Prima di utilizzare Ansible, è necessario assicurarsi che la **chiave privata SSH** utilizzata per accedere alle macchine AWS sia presente **nella directory principale del progetto**.

Se la chiave si trova in una posizione diversa, è necessario **modificare i file** `inventoryclient.ini` e `inventoryserver.ini`, aggiornando il valore del parametro `ansible_ssh_private_key_file` con il **percorso assoluto corretto** della chiave.

Successivamente, è necessario aggiornare i file `inventoryclient.ini` e `inventoryserver.ini` inserendo **l’indirizzo IP pubblico** delle rispettive macchine (client e server).  

### 2. Installazione dell’Ambiente Software

Una volta configurato l’accesso e gli IP, è possibile preparare le macchine installando i pacchetti e le dipendenze necessari tramite i seguenti comandi:

#### Installazione lato Server:

```bash
ansible-playbook -i inventoryserver.ini install_env.yml
```

#### Installazione lato Client:

```bash
ansible-playbook -i inventoryclient.ini install_env.yml
```

### 3. Deploy del Codice nelle Macchine AWS

⚠️ **Prima di eseguire il deploy**, è importante:

- Aggiornare l’indirizzo IP del server all’interno del progetto, utilizzando l’**IP pubblico della macchina AWS che fungerà da server**.
- Verificare che tutti i parametri di configurazione (es. **numero di test**, **numero di richieste**) siano coerenti con il tipo di test che si intende eseguire.

Una volta effettuate queste verifiche, è possibile trasferire le cartelle `server` e `client` nelle rispettive macchine eseguendo:

#### Deploy lato Server:

```bash
ansible-playbook -i inventoryserver.ini deploy_server.yml
```

#### Deploy lato Client:

```bash
ansible-playbook -i inventoryclient.ini deploy_client.yml
```

### 4. Permessi e Esecuzione

In ambiente **Linux**, a causa delle restrizioni sui permessi utente, è **consigliato assegnare i corretti permessi alle cartelle del progetto** con i seguenti comandi:

#### Sul Server:

```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/server
```

#### Sul Client:

```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/client
```

Infine, per evitare problemi di accesso o di scrittura durante i test, si consiglia di eseguire lo script `run_test.py` in modalità **sudo**:

```bash
sudo python3 run_test.py
```

---
