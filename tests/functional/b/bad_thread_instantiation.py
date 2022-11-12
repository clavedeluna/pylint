# pylint: disable=missing-docstring, redundant-keyword-arg, invalid-name
import threading


threading.Thread(lambda: None).run()  # [bad-thread-instantiation]
threading.Thread(None, lambda: None)
threading.Thread(lambda: None, group=None)  # [bad-thread-instantiation]
threading.Thread()  # [bad-thread-instantiation]

threading.Thread(group=None, target=lambda: None).run()
threading.Thread(group=None, target=None, name=None, args=(), kwargs={})
threading.Thread(None, None, "name")

def thread_target(n):
    print(n ** 2)


thread = threading.Thread(thread_target, args=(10,))  # [bad-thread-instantiation]
