import pickle
import os

DATA_DIR = '/data'

def save_state(state, state_pkl_file):
    path = f"{DATA_DIR}/{state_pkl_file}"
    with open(path, 'wb') as f:
        pickle.dump(state, f)

def load_state(state_pkl_file, default = {}):
    path = f"{DATA_DIR}/{state_pkl_file}"
    if(not os.path.exists(path)):
        return default
    with open(path, 'rb') as f:
        return pickle.load(f)


