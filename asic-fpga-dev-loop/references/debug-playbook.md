# 硬件 bug 调试手册（worked example：v3.13 writeback overlap 四连 bug）

这是真实调试战役的完整复盘：四个 bug 串联暴露、根因共享一个模式。
方法比结论更值钱——把每一步"怎么想到的"记下来。

## 背景与首次暴露

改动：Q-tile 边界在 final-microtile drain **发射时**（而非完成时）
退役，让 drain 与后继 tile 的计算重叠。三层仿真 + 回归 28/28 全绿，
board-case 只抽样跑了 L512（全对）——**上板后 L32 双模式、L128
causal bit mismatch**。

**教训一（流程级）：board-case 矩阵绝不抽样。** 长度 × 模式 ×
position base 组合各触发不同流水路径；28 项回归不含 board-case TB，
抽样 L512 放过了 L32/L128。放行上板的唯一标准 = 最终 RTL 上全矩阵
PASS。

## 第一步：VCS 复现 + 计数守恒定位范围

用 board-case 矩阵跑失败长度，VCS 稳定复现（与板上同位错）。关键
线索是**输出流长度守恒**：`output beats 37888 / expected 65536`。
65536/2048-beats-per-micro 推算：从某个 unit 起每个 tile 只流出
micro0，**27 个 micro1 的 drain 全部丢失**。计数守恒把"随机数据
损坏"和"系统性少做工作"区分开——后者是结构/协议 bug。

**消融实验**：把新机制整体置 0（`wb_overlap_advance=0`），全对——
问题确定在 overlap 路径内，排除 case 数据/环境。消融的作用是**圈定
搜索空间**，不是定位根因。

## 第二步：事件级 dump，健康/坏单元模式对比

在每个生命周期节点加边沿触发的 $display（launch/完成/退役/
mac_start，带完整上下文），对比健康单元与坏单元：

- 健康单元：`WBL(m0) → WBL(m1)+RETIRE 同拍 → OWD(tile_done)`
- 坏单元：`WBL(m0) → RETIRE（m1 未发射！）→ WBA_OFF nm=0`

**模式对比直接暴露"哪一步消失了"**（m1 的 launch），比盯着 RTL
读代码快得多。

## 第三步：触发源分解打印（多源条件必须打印每个输入）

RETIRE 的条件是三源或：`done || sticky || launched`。只打 RETIRE
无法归因——**多源条件出问题时，打印每个源在这一拍的值**（done/
sticky/launched 分别的边沿打印 + RETIRE 行内嵌快照）。本轮靠这个
锁定触发源是 `o_write_launched` 里折叠的 `o_write_done`（sticky
残留提前放走边界）。

## 四个 bug 与根因链（共享模式：一物两用 + 旧时序假设失效）

1. **launch 指针反噬 drain 游标**：`phaseb_norm_micro_idx` 兼任
   phaseb FSM 指针（PB_IDLE 每拍清零）和 drain 游标。旧串行流程
   drain 期间 FSM 停在 PB_DONE 从不清零；overlap 让后继 tile 的
   mac_start 在 drain 中进入 PB_IDLE → 游标被抹。修复：launch 时
   锁存 `wb_micro_q`，drain 侧（bank selector/l_state 索引/guard）
   全部改用锁存值。
2. **retire 清理竞态**：寄存器化 retire 脉冲晚一拍，buf_sel 已
   翻转，bank 清理打到预取刚填的新 bank。组边界走 LOAD_KV 复查
   ready 时暴露为 +7 重复请求；head 边界数据晚到时清了个空、
   KV_READ 不查 ready——同一竞态两种表相，数据仍对。修复：脉冲改
   推进当拍的组合输出（采样旧值）。
3. **sm_l_ctx slot-0 冲突**：单 micro tile 的 drain 读
   `sm_l_ctx[0]`，后继 tile 的首个 softmax 覆写同一 slot（2-micro
   的 drain 在 slot 1、后继从 slot 0 起步，天然错开）。修复：
   overlap 门控在 2-micro tile（单 micro 长度 host-bound 本无收益）。
4. **许可信号夹带杂散触发源**：`o_write_launched` 为防"drain 先于
   WRITE_O 完成"折叠了 `o_write_done`——sticky 残留让它提前放走
   边界，epoch 归零随即吞掉 m1 的发射槽。修复：只认锁存的
   `wb_last_drain_active`，其清零从 drain 结束改到下一 tile 的
   mac_start（retire 必然先于 mac_start，既不漏也不提前）。

## 可泛化的规则（已进 SKILL.md 红线）

- 跨流水段的许可信号 = 显式锁存许可证（发射置位、消费点清零），
  不复用含杂散脉冲/粘滞位的状态信号做或运算兜底。
- 一物两用的指针在时序改变后必反噬：段边界锁存副本。
- 新时序引入后，逐个审计受影响信号的采样点（旧值/新值、组合/
  寄存差一拍）。
- 流水段共享的 2-slot 上下文（m/l/ctx 类），按 slot 粒度审计重叠
  访问冲突；slot 没错开就阻塞或复制。
- 仿真与硬件的差异点（XPM 存储时序、真实 DMA 延迟、重启后的环境）
  是单独的 bug 类别，板上挂而仿真过 ≠ 环境问题，先查覆盖再查时序。

## 操作性陷阱（本轮实际踩到）

- 长仿真输出**重定向到文件**，不要 `| head` ——管道关闭触发
  SIGPIPE 会杀掉仿真，日志冻结在半途像挂死。
- debug $display 的格式串与参数数量必须一致（VCS 编译错报在
  最意想不到的位置）；删 RTL 信号后 grep 全部 TB 的 `dut.` 引用。
- /tmp 会被清：调试打印、ablation worktree、单 case 日志都要么
  落仓库归档、要么交接时写明重建步骤。
