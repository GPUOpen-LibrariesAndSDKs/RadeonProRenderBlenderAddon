import base64
from pathlib import Path


athena_bin = (Path(__file__).parent / "athena_bin.py").read_bytes()
athena_bin_encrypt = base64.standard_b64encode(athena_bin)

(Path(__file__).parent.parent / "rprblender/utils/athena.bin").write_bytes(athena_bin_encrypt)
