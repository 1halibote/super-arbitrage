import sys
import traceback

try:
    import backend.main
    print("SUCCESS")
except BaseException as e:
    with open("test_err.txt", "w") as f:
        traceback.print_exc(file=f)
