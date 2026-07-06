import sys

import torch

EXPECTED_PYTHON = (3, 12)
EXPECTED_TORCH = "2.12"
EXPECTED_CUDA = "12.6"


def check(label: str, ok: bool, detail: str = "") -> bool:
    status = "OK  " if ok else "FAIL"
    print(f"[{status}] {label}{': ' + detail if detail else ''}")
    return ok


results = []

# Python version
py_ver = sys.version_info[:2]
results.append(
    check(
        f"Python {EXPECTED_PYTHON[0]}.{EXPECTED_PYTHON[1]}",
        py_ver == EXPECTED_PYTHON,
        f"actual={py_ver[0]}.{py_ver[1]}",
    )
)

# PyTorch version
torch_ver = torch.__version__
results.append(
    check(
        f"PyTorch {EXPECTED_TORCH}",
        torch_ver.startswith(EXPECTED_TORCH),
        f"actual={torch_ver}",
    )
)

# CUDA availability
cuda_ok = torch.cuda.is_available()
results.append(check("CUDA available", cuda_ok))

# CUDA version
if cuda_ok:
    cuda_ver = torch.version.cuda or ""
    results.append(
        check(
            f"CUDA {EXPECTED_CUDA}",
            cuda_ver.startswith(EXPECTED_CUDA),
            f"actual={cuda_ver}",
        )
    )
    gpu_name = torch.cuda.get_device_name(0)
    results.append(check("GPU detected", True, gpu_name))

    # 기본 GPU 연산
    a = torch.tensor([1.0, 2.0, 3.0]).cuda()
    b = torch.tensor([4.0, 5.0, 6.0]).cuda()
    c = (a * b).sum().item()
    results.append(check("GPU tensor ops", abs(c - 32.0) < 1e-5, f"dot={c}"))
else:
    results.append(check("CUDA version", False, "CUDA not available"))
    results.append(check("GPU tensor ops", False, "CUDA not available"))

print()
passed = sum(results)
total = len(results)
print(f"결과: {passed}/{total} 통과")
if passed < total:
    print("실패 항목을 위 로그에서 확인하세요.")
