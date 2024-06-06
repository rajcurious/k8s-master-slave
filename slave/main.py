from flask import Flask, request, jsonify
import requests
import os
import time
import logging
app = Flask(__name__)
app = Flask(__name__)
from log_utils import get_logger


logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

service_name = os.getenv('SERVICE_NAME') 
master_url = f'http://{service_name}'

tasks = {}


@app.route('/add_task', methods=['POST'])
def add_task():
    task =  request.get_json()
    tasks['id'] = task
    logger.info(f"Task added {task}")
    return jsonify(task)

@app.route('/heartbeat')
def heart_beat():
    payload = {"alive": True}
    return jsonify(payload)

@app.route('/remove_task', methods=['POST'])
def remove_task():
    task =  request.get_json()
    tasks.pop(task['id'], None)
    logger.info(f"Task removed : {task}")
    return jsonify(task)

@app.route('/list_tasks')
def list_tasks():
    return jsonify(tasks)

def exponential_backoff_request(request_fn, max_attempts=5, initial_wait=1, max_wait=16):
    attempt = 0
    wait_time = initial_wait
    
    while attempt < max_attempts:
        try:
            return request_fn()
                         
        except requests.exceptions.RequestException as e:
            attempt += 1
            if attempt == max_attempts:
                logger.error(f"Max attempts reached. Failed to retrieve data: {e}")
                break
            logger.error(f"Attempt {attempt} failed: {e}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            wait_time = min(wait_time * 2, max_wait)  # Exponentially increase wait time
    
    return None

def connect_request():
    headers = {
        'Content-type':'application/json', 
        'Accept':'application/json'
    }
    payload = {
        'pod' :  os.getenv('POD_NAME')
    }
    url = f"{master_url}/connect"
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json() 

@app.route('/')
def index():
    pod_name = os.getenv('POD_NAME')
    return jsonify(pod_name)



if __name__ == '__main__':
    
    #setup initial connection with master node
    exponential_backoff_request(connect_request)

    app.run(host='0.0.0.0', port=80)

   