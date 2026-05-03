import sys
print("py:", sys.version, flush=True)
try:
    import torch
    print("torch:", torch.__version__, "cuda:", torch.cuda.is_available(), flush=True)
    if torch.cuda.is_available():
        print("device:", torch.cuda.get_device_name(0), flush=True)
        print("memMB:", torch.cuda.get_device_properties(0).total_memory // (1024*1024), flush=True)
    print("PROBE_OK", flush=True)
except Exception as e:
    print("PROBE_FAIL:", type(e).__name__, str(e)[:200], flush=True)
    sys.exit(1)
