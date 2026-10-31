# skills-of-Ip

这三个 skill 面向数字 IC/FPGA 项目的设计、验证、上板和多人 AI 协作：`asic-fpga-dev-loop` 负责硬件开发闭环，`asic-fpga-repo-layout` 负责仓库布局与交付证据，`projsync` 负责多人同步、任务范围和提交前状态。

## `asic-fpga-dev-loop`

负责 RTL/driver 修改后的完整迭代：

```text
设计修改 → Python golden → Verilator lint → VCS 回归
→ 全回归与 bit-exact → Vivado build → 上板测试 → 结果分析
```

它还规定板上错误的分流：环境问题修复板上设置、初始化脚本或镜像；RTL/逻辑问题优先在宿主机稳定复现，再定位、修复并重新验证；结果有效时检查统计口径和性能瓶颈。

配套文件包括：

- `scripts/board_run_template.sh`：板测流程模板。
- `scripts/lara_ssh.py`：通过 pexpect 完成 SSH、SCP、sudo 和密码保护。
- `references/debug-playbook.md`：硬件错误复现与定位案例。
- `references/lara-commands.md`：LARA 项目的命令示例。

## `asic-fpga-repo-layout`

负责数字 IC/FPGA 项目的目录职责、分支和证据归档。默认约定是：

- `hw/`：RTL 和构建脚本。
- `sw/`：驱动、板测、打包和初始化脚本。
- `docs/`：面向人的文档。
- `VV/`：testbench、回归、仿真和验证证据。
- `vivado_proj/`：Vivado 构建输出。
- `temp/`：板测和实验快照。
- `python_godel/`：Python golden model。

默认分支策略是 `develop` 保存全部开发内容，`master` 只保留最终可上板、可导出的已签核结果。构建证据需要记录源码 commit、时序和 DRC 摘要，以及 bit/hwh/xsa 的 SHA256。多人同步、claim、交接、commit 和 push 纪律由 `projsync` 负责。

## `projsync`

负责多人 AI 协作的状态同步。`docs/handle.md` 保存人工可读的项目状态和交接信息，`.projsync/claims/` 保存机器可读的作用域、所有权和验证记录。

命令包括：

- `sync`：同步远端并查看状态。
- `status`：查看分支、工作树和活动 claim。
- `start`：声明任务、文件范围和共享资源。
- `checkpoint`：记录命令、结果和验证证据。
- `finish`：完成 claim。
- `abort`：中止任务并记录原因。

编辑前需要确认远端、handle、memory、pitfalls、最近提交、分支、commit、工作树和 claim 状态。提交前更新 handle 和验证记录；本地 commit 与远程 push 分开，只有用户明确要求时才 push。`/projsync` 是明确触发词，其他两个 skill 主要按任务内容自动触发。

## 项目级个性化配置

项目可以在 `docs/project-overrides.md` 中覆盖默认开发闭环、文件组织或同步规则。只覆盖文件中明确写出的条目，未写出的内容继续使用默认规则；项目配置优先于 skill 默认值，但不能绕过用户明确指令、凭据保护、他人未提交修改保护和 push 授权要求。

模板见 [`docs/project-overrides.template.md`](docs/project-overrides.template.md)。
