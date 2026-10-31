---
name: asic-fpga-repo-layout
description: 数字 IC/FPGA 设计验证仓库的文件组织、证据归档和硬件项目分支产物约定；多人 AI 协作同步请使用 /projsync。
---

# 数字 IC/FPGA 仓库布局与证据

多人或 AI session 的接手、作用域 claim、远程同步、`handle.md`、commitlog、review、提交和 push 纪律统一由 `/projsync` skill 管理。本 skill 只定义硬件项目的目录归属、证据留存和交付分支语义；如果项目存在 `docs/project-overrides.md`，其中明确的目录和分支条目优先于本 skill 默认值；修改这些内容时先按 projsync 建立 claim。

## 目录布局

顶层按“硬件 / 软件 / 文档 / 验证 / 产物”切分，各目录职责单一：

```text
hw/       RTL 设计源码（rtl/ 按 core/mem/axi/pkg 分层；scripts/ 构建脚本）
sw/       软件：驱动、板上测试脚本、打包与初始化脚本、单元测试
docs/     文档（只放给人读的知识，不放可再生产物）
VV/       验证：testbench、回归与仿真脚本、仿真工作目录和证据归档
vivado_proj/  构建输出（按 build-tag 分目录）
temp/     板测/实验结果快照（按版本 tag 命名，独立目录互不覆盖）
python_godel/  golden model（数值参考实现）
```

放文件时遵循：可再生构建产物不进 `docs`；不可再生证据（板测快照、SHA256、事件日志）按版本或实验命名归档且永不覆盖。设计方向放设计文档，踩坑放 pitfalls，外部方案放 research 笔记，版本历史由项目的 handle/commitlog 维护。

## 分支与交付

默认约定 `develop` 保存全部开发内容，`master` 只保留最终可上板、可导出的已签核结果；项目可以在 `handle.md` 中声明不同命名。仿真、testbench、测试脚本和实验性改动只在 develop 中维护，未经完整硬件门禁的 RTL 不进入 master。develop 上的每个增量保留可回溯 commit；tag 必须指向真正交付的 commit，tag 后修复要移动 tag 并留下原因。本地 commit 与远程 push 分开，push 只有在用户明确要求时执行。构建输出是否入库由 `.gitignore` 明确声明，证据用哈希和路径记录。

`/projsync` 负责同步和提交前状态；本 skill 的硬件交付门禁通常包括 Python golden、Verilator lint、VCS 回归、bit-exact 全矩阵、Vivado 时序/DRC、板测和外部评测。各项目在 handle 中写明精确命令、通过标准、输入版本和证据路径，不能把 mock、仿真、硬件和外部评测混成一个结果。

## 证据与可追溯性

每个 bitstream 版本记录构建 commit、WNS/TNS/WHS/THS、DRC 摘要以及 bit/hwh/xsa 三件套 SHA256。每次板测归档结果目录、输入 case 哈希、运行脚本、环境快照和 bitstream 哈希；失败构建和作废 bitstream 也保留并明确标记。`/tmp` 会被清理，需续命的 diff 或日志要么进入归档，要么在 handle 中写重建步骤。

清理或 reset 前先确认不会删除不可再生证据。并行消融实验和候选方案使用独立 git worktree；实验结束后保存差异并清理 worktree 注册。

## LARA 示例

LARA 类项目可采用 `hw/rtl/{core,mem,axi,pkg}`、`sw/`、`VV/{tb,scripts,sim}`、`vivado_proj/build-<tag>/` 和 `temp/v<version>/`。板卡、license、初始化脚本和性能统计的具体操作由 `asic-fpga-dev-loop` 及其 references 提供。
