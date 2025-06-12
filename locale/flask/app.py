import os, json
from flask import Flask, jsonify, request

app = Flask(__name__)
ready_flag = False

@app.route('/')
def home():
    return jsonify(message="Hello, HTTPS world!")

@app.route('/ready', methods=['POST'])
def set_ready():
    global ready_flag
    ready_flag = True
    return jsonify(status="ready flag set")

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(ready=ready_flag)

@app.route('/plan', methods=['GET'])
def get_plan():
    try:
        plan_path = "/shared_plan/plan.json"
        if not os.path.exists(plan_path):
            return jsonify(error="File plan.json non trovato nel volume condiviso."), 404

        with open(plan_path, "r", encoding="utf-8") as f:
            plan = json.load(f)
        return jsonify(plan)
    except Exception as e:
        return jsonify(error=f"Errore nel recupero del piano: {e}"), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)