from flask import Flask, request, jsonify
import requests
import os
import time
import logging
from utils import load_state, save_state
app = Flask(__name__)
from log_utils import get_logger


logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)

service_name = os.getenv('SERVICE_NAME') 
master_url = f'http://{service_name}'
pod_name = os.getenv('POD_NAME')

TASKS_PICKLE_FILE = f"tasks_{pod_name}.pkl"

tasks = {}

# Flask App

@app.route('/')
def index():
    pod_name = os.getenv('POD_NAME')
    return jsonify(pod_name)

@app.route('/add_task', methods=['POST'])
def add_task():
    task =  request.get_json()
    logger.debug(f"Task add request json:  {task}")
    task_id = task['id']
    tasks[task_id] =  task
    logger.info(f"Task added {task}")
    save_state(tasks, TASKS_PICKLE_FILE)
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
    save_state(tasks, TASKS_PICKLE_FILE)
    return jsonify(task)

@app.route('/list_tasks')
def list_tasks():
    return jsonify(tasks)

@app.route('/task_ids')
def task_ids():
    data = {'task_ids' : list(tasks.keys())}
    return jsonify(data)

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




if __name__ == '__main__':
    
    #setup initial connection with master node
    exponential_backoff_request(connect_request)

    tasks = load_state(TASKS_PICKLE_FILE)

    app.run(host='0.0.0.0', port=80)

   