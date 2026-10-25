from collections.abc import Callable
from typing import Any


# Recieve arguments for decorator function
def custom_fence(fence: str = "+"):
    # decorator function
    def add_fence(func: Callable[[Any], None]):
        # Original function wrapper
        def wrapper(text: str):
            print(fence * len(text))
            func(text)
            print(fence * len(text))
        return wrapper
    return add_fence

@custom_fence("-")
def log(text: str):
    print(text)
    

log("ballon")