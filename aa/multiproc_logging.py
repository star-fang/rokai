import time
import random
import multiprocessing
import logging
from logging.handlers import QueueHandler, QueueListener

def f(i):
    time.sleep(random.uniform(.01, .05))
    logging.info('function called with {} in worker thread.'.format(i))
    time.sleep(random.uniform(.01, .05))
    return i

def worker_init(q):
    q_handler = QueueHandler(q)
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(q_handler)
    logging.info('worker initialized')

def logger_init():
    q = multiprocessing.Queue()
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(levelname)s: %(asctime)s - %(process)s - %(message)s'))

    q_listener = QueueListener(q, handler)
    q_listener.start()

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    return q_listener, q

def main():
    q_listener, q = logger_init()

    logging.info('hello')
    pool = multiprocessing.Pool(4, worker_init, [q])
    for result in pool.map(f,range(10)):
        pass

    pool.close()
    pool.join()
    q_listener.stop()

if __name__ == '__main__':
    main()
