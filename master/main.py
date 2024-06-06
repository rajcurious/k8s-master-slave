from flask import Flask, jsonify, request
import os
import logging
from log_utils import get_logger
import requests
from apscheduler.schedulers.background import BackgroundScheduler


# Create a lock object
import threading
lock = threading.RLock()

app = Flask(__name__)

logger = get_logger(__name__)
logger.setLevel(logging.DEBUG)
# pod_name : {tasks: []}
slaves = {}
slave_service_name = os.getenv('SLAVE_SERVICE_NAME')

slave_url = "{}" +  f".{slave_service_name}.default.svc.cluster.local"

# pod_name:  # of tasks
slave_tasks_freq = {}

#task_id, task

tasks = {}

#task_id, task
unassigned_tasks = {}

#task_id, pod_name
task_assign_map = {}

# Create an instance of BackgroundScheduler
scheduler = BackgroundScheduler()

task_counter = 0

def health_check():
    with lock:
        pods = list(slaves.keys())
        for pod_name in pods:
            is_alive = check_heartbeat(pod_name)
            if(not is_alive):
                remove_slave(pod_name)

def distribute_tasks():
    with lock:
        n = len(tasks)
        if(n == 0): return
        assigned_tasks = []
        for task_id, _  in unassigned_tasks.items():
            slave_tasks_freq_sorted = sorted(slave_tasks_freq.items(), key=lambda item: item[1], reverse=False)
            for pod_freq_pair in slave_tasks_freq_sorted:
                is_task_assigned = assign_task(pod_freq_pair[0], task_id)
                if(is_task_assigned):
                    assigned_tasks.append(task_id)
                    break
        for task_id in assigned_tasks:
            unassigned_tasks.pop(task_id)

        min_tasks = n  // len(slaves)
        surplus_tasks = []
        
        for pod_name, slave in slaves.items():
            while(len(slave['tasks']) > min_tasks):
                task_id = slave['tasks'].pop()
                slave_tasks_freq[pod_name]-=1
                surplus_tasks.append(task_id)
            

        for task_id in surplus_tasks:
            slave_tasks_freq_sorted = sorted(slave_tasks_freq.items(), key=lambda item: item[1], reverse=False)
            for pod_freq_pair in slave_tasks_freq_sorted:
            
                curr_assigned_pod_name = task_assign_map[task_id]
                if(slave_tasks_freq[curr_assigned_pod_name] <= pod_freq_pair[1]):
                    slave_tasks_freq[curr_assigned_pod_name]+=1
                    slaves[curr_assigned_pod_name]['tasks'].append(task_id)
                    break
                else:
                    is_task_assigned = assign_task(pod_freq_pair[0], task_id)
                    if(is_task_assigned):
                        deassign_task(curr_assigned_pod_name, task_id)
                        break


def assign_task(pod_name, task_id):
    with lock:
        task = tasks[task_id]
        
        if(task_id in task_assign_map and task_assign_map[task_id] == pod_name):
            return True
        try:
            url = slave_url.format(pod_name)
            headers = {
            'Content-type':'application/json', 
            'Accept':'application/json'
            }
            response = requests.post(f"http://{url}/add_task", json=task, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors

            slaves[pod_name]['tasks'].append(task_id)
            slave_tasks_freq[pod_name]+=1
            task_assign_map[task_id] = pod_name
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Exception {e} while assigning task {task}")
            return False
    

def deassign_task(pod_name, task_id):
    with lock:
        task =  tasks[task_id]
        try:
            url = slave_url.format(pod_name)
            headers = {
            'Content-type':'application/json', 
            'Accept':'application/json'
            }
            response = requests.post(f"http://{url}/remove_task", json=task, headers=headers)
            response.raise_for_status()  # Raise an exception for HTTP errors

            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Exception {e} whiled deassigning task {task}")
            return False
    

def check_heartbeat(pod_name):

    try:
        url = slave_url.format(pod_name)
        response = requests.get(f"http://{url}/heartbeat")
        response.raise_for_status()  # Raise an exception for HTTP errors

        return True
    except requests.exceptions.RequestException as e:
        return False

    

def remove_slave(pod_name):
    logger.info(f"Removing slave pod : {pod_name}")
    with lock:
        if(pod_name in slaves):
            task_ids = slaves[pod_name]['tasks']
            slaves.pop(pod_name, None)
            for task_id in task_ids:
                unassigned_tasks[task_id] = {}
                task_assign_map.pop(task_id)
           
        slave_tasks_freq.pop(pod_name)

distribute_tasks_interval = int(os.getenv('DISTRIBUTE_TASKS_INTERVAL'))
health_check_interval = int(os.getenv('HEALTH_CHECK_INTERVAL'))

# Schedule the health check function to run every minute
scheduler.add_job(distribute_tasks, 'interval', seconds=distribute_tasks_interval)

scheduler.add_job(health_check, 'interval', seconds=health_check_interval)


# REST APIs
@app.route('/')
def index():
    pod_name = os.getenv('POD_NAME')
    return jsonify(pod_name)

@app.route('/slaves')
def get_slaves():
    return jsonify(slaves)

@app.route('/task_map')
def get_task_assign_map():
    return jsonify(task_assign_map)

@app.route('/connect', methods=['POST'])
def connect():
    with lock:
        request_json =  request.get_json()
        pod_name = request_json['pod']
        logger.info(f"Connection request :  {request_json}")
        if(pod_name not in slaves):  
            slaves[pod_name] = {'tasks': []}
            slave_tasks_freq[pod_name] = 0

        return jsonify(slaves[pod_name])

@app.route('/remove_task', methods=['POST'])
def remove_task():
    with lock:
        task_remove_req =  request.get_json()
        task_id =  task_remove_req['id']
        pod_name =  task_assign_map[task_id]
        deassign_task(pod_name, task_id)
        slave_id = task_assign_map.pop(task['id']) # slave_id =  pod_name
        task = tasks.pop(task_id)
        slave_tasks_freq[slave_id] -= 1
        return jsonify(task)

@app.route('/add_task', methods=['POST'])
def add_task():
    global task_counter
    with lock:
        task =  request.get_json()
        task_id = task_counter
        task['id'] = task_id
        task_counter += 1
        tasks[task_id] = task
        unassigned_tasks[task_id] = {}
        return jsonify(task)
    
@app.route('/call_slave', methods=['POST'])
def call_slave():
    request_json =  request.get_json()
    pod_name = request_json['pod']
    url = slave_url.format(pod_name)
    response = requests.get(f"http://{url}/heartbeat")
    return jsonify(response)

        

if __name__ == '__main__':
    pod_name = os.getenv('POD_NAME')
    logging.error(pod_name)
    scheduler.start()
    app.run(host='0.0.0.0', port=80)
