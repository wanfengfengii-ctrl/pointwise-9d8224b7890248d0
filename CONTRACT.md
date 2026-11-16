# 正常业务契约

## 数据与使用边界

本地维护窗口单工作者，Archive 可关闭后重开，也可有顺序使用的多个对象。接口不承诺线程共享连接或并发调度。所有 ID 为正整数；名字、单元键及请求 ID 为非空字符串。单元身份由网格修订 ID 与单元键共同确定。没有投影、球面、容差或浮点几何语义。

网格 cells 是非空 dict：cell -> [closed_walk, ...]；walk 至少有两个点且首尾坐标相等，point 为两个有理数。允许冗余点和往返线迹，所有声明的输入边均计入 40 条上限。只有共同奇偶填充的正面积部分属于单元。任何两个不同单元交叠面积必须为零。环方向、起点和共线分段不改变面域；输入原文写法仍独立留存。

grids.body 保存输入坐标经 str 后的原始字符串，包含如 0/2 的拼写；read_grid.raw 返回这些字符串，read_grid.cells 返回 Fraction 顶点。输入映射经键排序序列化，环序和顶点序保留。SDK1 仅导出 Region.area() 和 Region.intersection_area(other) 标量运算；内部边界求积不提供面域分解。

fields.body 保存逐单元 Fraction 的规范字符串或 null。总量可为负、有理数或零；None 独立表示缺测。观测对所属修订的单元必须完整且精确匹配，不能以其他修订的键补齐。没有隐式补零或按 head 解释历史观测。

## 公开入口与错误

Archive(path=":memory:", fault=None) 建立 SDK1 归档，支持 with；close() 关闭。路径的父目录由调用方创建。:memory: 的寿命为该连接。

- publish_grid(name, request, cells) -> revision：发布不可变几何修订并移动该名字的 head，回执与 head 同事务提交。相同请求及相同序列化内容返回原 ID，即使 head 已更新也不恢复旧 head。请求内容含网格名及坐标原文；等值但拼写不同的坐标属于不同请求内容。
- head(name) -> revision；read_grid(revision) -> {id, name, cells, raw}；grid_receipt(request) -> revision。
- put_field(request, grid, values) -> version：创建不可变观测版本。请求内容按 grid 和规范有理数值比较；等价分数字符串可重放。回执与版本同事务提交，网格和观测请求 ID 各自有独立命名空间。
- read_field(version) -> {id, grid, values}；field_receipt(request) -> version。
- create_job(name, source, target, field) -> job：保存三个明确的修订/版本引用，field.grid 必须等于 source。不使用名字追随 head。同名同绑定返回原 ID，同名不同绑定报 Conflict。
- read_result(job) -> {job: {id, name, source, target, field}, result_id, result}：未运行时后二者均为 None，未知任务报 NotFound。
- run_job(job) -> 同 read_result：按固定绑定重算并发布新结果 ID。成功重跑保留同样数值，但增加一次结果记录并移动任务的结果指针。无部分结果读取接口。

ValidationError 表示非法输入、零面积、内域重叠或绑定不匹配；Conflict 表示请求或任务名已绑定不同内容；NotFound 表示未知修订、版本、任务、名字或回执。它们分别继承 ValueError、ValueError、LookupError。SQLite 与故障钩子的异常原样传播。无效写入不新增业务版本或回执，失败不移动 head 或已有结果指针。调用方不得直接改库内不可变表。

## 计算与结果

源观测 v 是源逻辑单元完整面域的总量。对源 s 与目标 t，A(s,t) 是精确交叠面积，A(s)>0。transfers[s][t] = v(s)*A(s,t)/A(s)。目标单元内域不重叠，因此逐源已分配量加 uncovered[s] 恰等于 v(s)，含负数也使用此等式。

result 的所有数值为 Fraction：
- allocated：全部目标单元 -> 数值分配合计，含数值零。
- source_area：全部源单元 -> 完整面积。
- overlap_area：全部源 -> 全部目标 -> 交叠面积，保留零。
- transfers：非缺测源 -> 全部目标 -> 数值分配量，保留零。
- uncovered：非缺测源 -> 未覆盖总量。
- missing_area：缺测源 -> 有正交叠的目标 -> 缺测交叠面积；即使该源无交叠也保留空 dict。
- uncovered_missing_area：缺测源 -> 未覆盖面积。

缺测源不会出现在 transfers/uncovered；数值零源不会出现在 missing_area。结果中的面积与总量不混合相加。结果在 results 表不可变保存；jobs.result 仅在整次计算成功后移动。Fraction 序列化为带类型标记的分子分母，读取恢复精确类型。

## 存储及失败边界

metadata.version=1。grids/heads/grid_receipts、fields/field_receipts、jobs、results 保存上述真实业务关系并启用外键。无删除和历史重绑定接口。输入和引用校验在写入前完成，写入使用 BEGIN IMMEDIATE 事务；结果插入与指针更新同事务完成。

fault(event) 为同步故障注入设施；公开事件见 README。钩子只出现在真实操作内部。提交前抛错会回滚整笔写入，原异常传播。成功提交后才返回。重新打开后的查询与已提交状态一致，失败操作可重新请求。注入测试验证异常回滚，不声称其等同于进程终止测试。

## 独立凸形端口

gridarchive.vendor.sdk2.Polygon(vertices) 接受一个正面积凸多边形，首尾可显式重复，其余顶点互异；可顺时针或逆时针，可含顺序共线点。凸性采用全部顶点位于每条有向边同侧的精确判定。退化、自交及凹形报 ValidationError。

Polygon.vertices 为规范逆时针 Fraction 顶点；area() -> Fraction；intersection(other) -> Polygon 或 None；intersection_area(other) -> Fraction。边界或点接触返回零面积/None。端口没有环、洞、奇偶填充、逻辑单元、数据库或面域分解 API。独立端口用例见 tests/test_sdk2.py。正常归档业务仅调用 SDK1。
