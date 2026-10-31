#!/bin/bash
# board_run_template.sh — 板测套件骨架（按项目替换 <占位> 后使用）
# 经验固化的不变式：
#   1. 首步必须是 clear cache / dtbo 初始化（重启后 fabric 不自动加载）
#   2. sudo 显式注入环境（XRT 路径等），性能口径显式固定
#   3. 独立输出目录，先 rm -rf 再跑，结尾 chmod a+rX 便于取回
#   4. 每步 echo RC，日志尾部可机读判定
set -u
cd <BOARD_PAYLOAD_DIR>
SUDO_PY='sudo env <XRT_ENV> <MODE_PINS> <VENV_PYTHON>'

sudo rm -rf <RESULTS_1> <RESULTS_2> <PERF_DIR>
echo '=== [1/4] clear pynq cache (dtbo) ==='
$SUDO_PY clear_pynq_cache.py
echo '=== [1b/4] minimal smoke (one case) ==='
# 先用最小 case 冒烟确认 overlay/链路活着，再跑全矩阵
$SUDO_PY board_matrix.py --bitstream ./<BIT> --cases <CASES_A> \
  --output-dir ./<SMOKE_DIR> --lengths 1 --causal-only
echo "SMOKE_RC=$?"
echo '=== [2/4] functional matrix A ==='
$SUDO_PY board_matrix.py --bitstream ./<BIT> --cases <CASES_A> \
  --output-dir ./<RESULTS_1> --lengths 1 16 32 64 128 512
echo "MATRIX1_RC=$?"
echo '=== [3/4] functional matrix B ==='
$SUDO_PY board_matrix.py --bitstream ./<BIT> --cases <CASES_B> \
  --output-dir ./<RESULTS_2> --lengths 1 16 32 64 128 512
echo "MATRIX2_RC=$?"
echo '=== [4/4] perf A/B (single variable vs baseline) ==='
$SUDO_PY board_performance.py --bitstream ./<BIT> \
  --case-set a=<CASES_A> --case-set b=<CASES_B> \
  --output-dir ./<PERF_DIR> --warmup 1 --repeats 5 \
  --lengths 1 16 32 64 128 --cpu-core 3 --cpu-clock-mhz 1333.333
echo "PERF_RC=$?"
sudo chmod -R a+rX <RESULTS_1> <RESULTS_2> <PERF_DIR> 2>/dev/null
echo 'ALL_STEPS_DONE'
