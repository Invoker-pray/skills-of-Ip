# LARA 项目具体命令与坑（实例参考）

工作目录 `/home/jiao/git/LARA`。以下为该项目的实测命令模板；其他项目
按同样结构替换路径/参数。

## 三层仿真门禁

```bash
# Python golden（期望 7/7）
.venv/bin/python3 python_godel/attention_golden.py --test-all
# sw 单元测试（期望 45/45）
.venv/bin/python3 -m unittest discover -s sw/tests

# Verilator lint（判据：与 HEAD 归一化 diff 为空；HEAD 上有 133 条
# pre-existing 噪声，SHORTREAL/UNUSEDSIGNAL/UNUSEDPARAM 等，勿用
# +define+SYNTHESIS——反而 195 条）
verilator --lint-only -Wall --timing --top-module attn_top \
  hw/rtl/pkg/attn_pkg.sv hw/rtl/axi/attn_axi_lite_slave.sv \
  hw/rtl/axi/attn_axi_stream_sink.sv hw/rtl/axi/attn_axi_stream_source.sv \
  hw/rtl/core/attn_core.sv hw/rtl/core/attn_tile.sv hw/rtl/core/bf16_mac.sv \
  hw/rtl/core/psum_accum.sv hw/rtl/core/softmax_engine.sv \
  hw/rtl/mem/kv_cache_ram.sv hw/rtl/mem/output_buffer.sv \
  hw/rtl/mem/tile_buffer.sv hw/rtl/attn_top.sv

# VCS 全量回归（gcc16 需要 -Wno-error=implicit-function-declaration shim）
mkdir -p /tmp/lara_gcc_wrapper
printf '#!/bin/bash\nexec /usr/bin/gcc -Wno-error=implicit-function-declaration "$@"\n' > /tmp/lara_gcc_wrapper/gcc
chmod +x /tmp/lara_gcc_wrapper/gcc
export PATH=/tmp/lara_gcc_wrapper:$PATH
RUN_SYNTH_PATHS=1 RUN_XPM_PATHS=1 bash VV/scripts/run_regression.sh
# 判定：Passed: 28 / 28 + ALL TESTS PASSED（空日志+exit 255 = license 没开）

# bit-exact board-case 矩阵（两组 × 全长度，绝不抽样）
bash VV/scripts/run_tb_attn_top_board_matrix.sh board_cases_rtl_contract_v2.6_q31_kv7 "1 16 32 64 128 512"
bash VV/scripts/run_tb_attn_top_board_matrix.sh board_cases_rtl_contract_v2.6_q3_kv3 "1 16 32 64 128 512"

# 单 case（调试用）
CASE_PATH=board_cases_rtl_contract_v2.6_q31_kv7/case_L32_q31_kv7_noncausal.npz \
BOARD_CASE_TEST_SEQ=32 BOARD_CASE_CAUSAL=0 CASE_Q_POS_BASE=31 CASE_KV_POS_BASE=7 \
bash VV/scripts/run_tb_attn_top_board_case.sh > /tmp/run.log 2>&1
```

环境：VCS_HOME/license 由 ~/.zshrc 提供（27000@127.0.0.1）；XPM 类
TB 需要 gcc shim（见上）。**改 RTL 后勿直接复用旧 simv 目录**。

## Vivado 构建

```bash
LARA_BUILD_TAG=<版本>_$（date +%Y%m%d） bash hw/scripts/vivado_build.sh
```

判定看 `reports/post_route_timing_summary.rpt`（WNS/TNS/WHS/THS）、
`post_route_drc.rpt`、`deploy/` 三件套 SHA256。build_metadata.txt 记录
git HEAD 与状态。

## 上板

- 板：ubuntu@192.168.2.100；密码仅经环境变量 `LARA_BOARD_PW` 进
  pexpect，永不落盘。
- 打包：`bash sw/package_kv260_board.sh <build-dir> <payload-dir> <sd-bundle>`
  之后**手动**补 case 目录（脚本只打印提示不代拷），重生成
  LARA_SHA256SUMS（`find . -type f ! -name LARA_SHA256SUMS | xargs sha256sum`），
  本地与板上各校验一次。
- pexpect helper（/tmp/lara_ssh.py，会丢需重建）要点：scp 参数顺序
  `scp <src> <dst> [-r]`；sudo 走 `ssh -tt` + `expect(["\\[sudo\\] password"])`
  （`[sudo]` 不转义是字符类，永远匹配不上）；发送密码瞬间关
  logfile_read；后台跑要 `sys.stdout.reconfigure(line_buffering=True)`；
  /tmp 重启即清。
- 板测脚本骨架（首步必须是 clear_pynq_cache——重启后 zocl 不自动
  加载，否则全 case ENODEV 假 FAIL；全矩阵前先跑一个最小 case 冒烟
  确认 overlay 链路，再决定是否值得跑 20+ 分钟的全套）：
  ```bash
  SUDO_PY='sudo env XILINX_XRT=/usr BOARD=KV260 LARA_REQUEST_MODE=poll /usr/local/share/pynq-venv/bin/python3'
  $SUDO_PY clear_pynq_cache.py
  $SUDO_PY board_matrix.py --bitstream ./lara_attention.bit --cases <dir> \
    --output-dir ./board_results_<tag> --lengths 1 16 32 64 128 512
  $SUDO_PY board_performance.py --bitstream ./lara_attention.bit \
    --case-set a=<dir> --case-set b=<dir2> --output-dir ./board_perf_<tag> \
    --warmup 1 --repeats 5 --lengths 1 16 32 64 128 \
    --cpu-core 3 --cpu-clock-mhz 1333.333
  ```
- 性能 A/B 单变量原则；执行用户变化本身就是变量（root 会让 driver 的
  request mode auto 解析成 irq）——口径显式固定 `LARA_REQUEST_MODE=poll`。
- sudo 产生的输出目录 root-owned，取回前 `chmod -R a+rX`；重跑前
  `sudo rm -rf`。
- 进板先看状态：`uptime`（判断是否重启→dtbo 必未加载）、
  `xbutil examine`、`lsmod | grep zocl`。
- 结果归档：独立 temp/ 目录存 summary/profile/actual NPZ/运行脚本/
  环境；独立审计一遍 bit-exact（actual vs expected 逐位）+ profile
  守恒式（total==stall+core）。
