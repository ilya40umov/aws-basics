#!/bin/usr/env python3

import os
import socket
import threading
import time
import atexit
import boto3

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask


app = Flask(__name__)

cron = BackgroundScheduler()
cron.start()
atexit.register(lambda: cron.shutdown(wait=False))

if os.environ.get('USE_LOCALSTACK'):
    import localstack_client.session
    session = localstack_client.session.Session()
    cloudwatch = session.client('cloudwatch')
else:
    cloudwatch = boto3.client('cloudwatch', region_name='eu-west-1')


@cron.scheduled_job('interval', minutes=1)
def report_in_flight_count_to_cloudwatch():
    response = cloudwatch.put_metric_data(
        MetricData = [
            {
                'MetricName': 'ComputationsInFlight',
                'Dimensions': [
                    {
                        'Name': 'Hostname',
                        'Value': socket.gethostname()
                    }
                ],
                'Unit': 'None',
                'Value': Computation.in_flight_count()
            },
        ],
        Namespace='FlaskBackgroundComputationsApp'
    ) 
    print(response)


@app.route('/')
def index():
    return f"Number of computations running: {Computation.in_flight_count()}\n"


class Computation(threading.Thread):
    
    _in_flight_count_guard = threading.Condition()
    _in_flight_count = 0
    
    def __init__(self):
        super(Computation, self).__init__(daemon=True)

    def run(self):
        with self.__class__._in_flight_count_guard:
            self.__class__._in_flight_count += 1
        print("Started computation")
        time.sleep(120) 
        print("Finished computation")
        with self.__class__._in_flight_count_guard:
            self.__class__._in_flight_count -= 1
   
    @classmethod
    def in_flight_count(cls) -> int:
        with cls._in_flight_count_guard:
            return cls._in_flight_count


@app.route('/start_computation', methods=['POST'])
def start_computation():
    in_flight = Computation.in_flight_count() 
    Computation().start()
    return f"Launched the computation in background. In total running: {in_flight + 1}\n"
