# 控制重网格交接不变量

本文件记录按 CONTROLLED.md 交付的控制任务归档与约束执行所依赖的固定不变量，供后续维护者核账。所有数值（面积、先验、流量、偏差、范围端点与见证）均为 `fractions.Fraction`，全程无浮点容差。

## 1. 绑定与归档不变量

- `create_controlled_job(name, source, target, field, control)` 冻结四个**身份 ID**（均为正整数），不接受网格名或 head。`field.grid == source`、`control.grid == target` 在创建时校验。
- 创建时额外校验：源观测逐单元非 `None` 且非负；控制观测中非 `None` 的值非负（`None` 是不约束，`0` 是必须恰好满足的零控制）。违反抛 `ValidationError`，不新增任务；未知身份抛 `NotFound`。
- 普通任务表 `jobs` 与控制任务表 `controlled_jobs` 是**独立命名空间**，同名可分别存在；同名同绑定重放返回原任务 ID，同名异绑定抛 `Conflict`。没有修改或删除绑定的入口。
- 新表 `controlled_jobs`、`controlled_results` 以 `CREATE TABLE IF NOT EXISTS` 增补；打开旧样例数据库时旧表、旧数据与普通任务行为完全不变，外键保持开启。
- 源守恒与目标控制的矛盾是数学无解而非非法参数：任务允许创建，执行时抛 `gridarchive.Infeasible`（继承 `ValueError`），且不发布任何结果，读取仍为未运行。

## 2. 支持与流量不变量

- 仅当交叠面积 `A_st > 0` 时源 `s` 可向目标 `t` 发送非负流量 `x_st`；点/线接触与零面积交叠没有流量变量，固定为零，也不出现在 `ranges.transfers` 中。
- 仅当未覆盖面积 `U_s = A_s - Σ_t A_st > 0` 时该源才有非负未覆盖出口 `u_s`；其他源的未覆盖流量固定为零，且不进入 `ranges.uncovered`。
- 面积只决定**支持与先验**，不是容量：一条正面积边可承载该源的全部总量。未覆盖出口保留源身份，不是跨源兜底。
- 源守恒：每条源的全部允许流量（含其未覆盖出口）之和恰等于源观测值。目标控制：每个非 `None` 控制目标的流入之和恰等于控制值；不约束目标仍只能收到空间支持允许的流量。

## 3. 最优性与范围不变量

- 先验：`p_st = v_s A_st / A_s`，未覆盖先验 `q_s = v_s U_s / A_s`。目标是在所有可行分配中最小化 `C = Σ允许流量 |流量 − 先验|`。
- 生产求解器 `gridarchive/lp.py` 是纯 `Fraction` 两阶段单纯形（Bland 规则保证有限终止），用偏差变量加两条非负松弛把绝对值精确线性化；无解在第一阶段以人工变量残量非零判定。
- 求得最优 `C*` 后，追加等式“目标行 · 变量 = C*”把后续求解钉在同一最优面上；对每条允许流量分别最小化、最大化，得到该流量在**全部最优分配**中的精确 `min`、`max`。
- 每个端点都附一份**完整**最优分配作见证，见证独立满足支持、非负、源守恒、目标控制且偏差恰为 `C*`。独立范围端点不保证可同时达到，禁止把不同流量的端点拼成联合解（ambiguous 例中两源同取 t1 上端点会得 6，违反控制 4）。
- `min == max` 时仍保留两份可独立读取的见证；源值为零的正面积支持仍报告 `[0,0]`。

## 4. 发布、失败与重开不变量

- 结果插入与 `controlled_jobs.result` 指针移动在同一 `BEGIN IMMEDIATE` 事务；`result.after_insert`、`result.before_commit` 均在提交前触发，`job.before_commit` 覆盖任务创建。
- 钩子或存储异常原样传播并整体回滚：首跑失败保持未运行、无候选结果；已有成功结果时失败保留上次完整结果与原指针；创建失败不新增任务。
- 成功重跑生成新结果 ID、移动指针，但 `result` 数值完全相同；关闭重开后已提交状态一致。同名网格替换、新观测发布都不改变旧任务的四个冻结身份与重跑数值。
- 读取经 JSON + Fraction 类型标记深拷贝，调用方修改返回对象不会影响持久结果或后续读取。

## 5. 独立小例核账

- `tests/controlled_reference.py` 是**不导入生产求解器**的独立参照：仅用 Fraction 高斯消元，枚举平衡/控制等式与各 kink 超平面 `x_k = p_k` 细化多面体的全部基本可行解，直接计算绝对偏差，独立给出可行性、最优成本与每条流量的最优面范围。
- `tests/test_controlled_reference.py` 用两个固定随机种子生成小型精确几何，逐例比对两个独立方法的可行性、成本、范围及每个端点见证的可达性与最优性；覆盖无解、未覆盖出口、不约束/零控制、有理数与全零源。
- `controlled_examples.py` 的四个手算例（ambiguous、unsupported、free_and_outside、zero_and_touch）由 `tests/test_controlled.py` 与 `verify_controlled.py` 按文档期望值核账。
- 运行入口：`python3.11 -B -m unittest discover -s tests -t . -v`（含原 27 个未改动测试）随后 `python3.11 -B -m verify_controlled`；演示 `python3.11 -B -m gridarchive demo`。
