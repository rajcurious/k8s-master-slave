# Master slave system on k8s

A system  which dynamically and optimally distributes the tasks to the slave nodes.

## Components

1. Master node : An external facing service exposing APIs like /add_task, /remove_task. It uniformally distributes the tasks assigned by the user agent among the slave nodes.
2. Slave nodes : An internal service which receives the tasks assigned by the master node

## System:
The system is build for k8s, master is k8s NodePort service, whereas slaves are group of k8s statefullset as headless service. Any new slave sends connect signal to master, master registers that slave and periodically sends health-check heartbeat signal. Master uniformally distribute the tasks among the registered slaves.

