# https://stackoverflow.com/a/54884881/1065654

import signal
import threading
import time


class ProgramKilled(Exception):
    """
    An instance of this custom exception class will be thrown every time we get
    a SIGTERM or SIGINT
    """
    pass


# Raise the custom exception whenever SIGINT or SIGTERM is triggered
def signal_handler(_signum, _frame):
    raise ProgramKilled


# https://stackoverflow.com/questions/2697039/python-equivalent-of-setinterval
class IntervalThread(threading.Thread):
    def __init__(self, interval, action, *_args, **_kwargs):
        super(IntervalThread, self).__init__()
        self.interval = interval
        self.action = action
        self.stopEvent = threading.Event()

    def run(self):
        next_time = time.time() + self.interval
        while not self.stopEvent.wait(next_time - time.time()):
            next_time += self.interval
            self.action()

    def cancel(self):
        self.stopEvent.set()


def __main():
    # Handle SIGINT and SIGTERM with the help of the callback function
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Record the time for the purposes of demonstration
    start_time = time.time()

    def action():
        print('action ! -> time : {:.1f}s'.format(time.time() - start_time))

    # start action every 1s
    inter = IntervalThread(1, action)
    print('just after setInterval -> time : {:.1f}s'.format(
        time.time() - start_time))

    # will stop interval in 500s
    t = threading.Timer(500, inter.cancel)
    t.start()

    # https://www.g-loaded.eu/2016/11/24/how-to-terminate-running-python-threads-using-signals/
    while True:
        try:
            time.sleep(1)
        except ProgramKilled:
            print("Program killed: running cleanup code")
            inter.cancel()
            break


if __name__ == "__main__":
    __main()
