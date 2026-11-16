# 面域观测归档

Python 3.11 标准库实现。数据员发布面域网格、为指定修订入账单元总量，随后创建固定版本的守恒重网格任务。几何和结果使用 Fraction，SQLite 保存修订、head、观测版本、请求回执、任务与每次完整结果。

运行完整回归和演示：

```sh
python3.11 -B -m unittest discover -s tests -t . -v
python3.11 -B -m gridarchive demo
```

演示只在 TemporaryDirectory 内创建数据库，展示凹单元总量 12 向面积 1 和 3 的目标分配为 3 和 9，独立缺测面积、含洞新修订、自交单元以及重开后旧任务的固定绑定。无需安装依赖。

## 公开 Python API

```python
from gridarchive import Archive
from gridarchive.samples import rectangle

with Archive("observations.sqlite") as archive:
    source = archive.publish_grid("source", "source-request", {
        "unit": [rectangle(0, 0, 2, 2)]})
    target = archive.publish_grid("target", "target-request", {
        "half": [rectangle(0, 0, 1, 2)]})
    field = archive.put_field("field-request", source, {"unit": 12})
    job = archive.create_job("delivery", source, target, field)
    result = archive.run_job(job)
    assert result["result"]["allocated"]["half"] == 6
    assert result["result"]["uncovered"]["unit"] == 6
```

输入环显式闭合；单元的所有环共同按奇偶规则填充，不依赖环方向。支持凹形、洞、自交与共线重合。线迹面积为零。每份网格至多 40 条输入边；单元须有正面积，单元间内域不能重叠，共边和点接触允许。坐标和数值接受 int、Fraction、Fraction 可解析字符串，拒绝 float 和 bool。完整接口、结果和异常见 CONTRACT.md。

职责位置：
- gridarchive/grids.py：不可变网格修订、原始环、head、发布回执。
- gridarchive/fields.py：绑定修订的完整观测与回执，区分零和缺测。
- gridarchive/jobs.py：固定绑定及已发布结果读取。
- gridarchive/remap.py：精确分配、逐源明细和结果原子发布。
- gridarchive/storage.py：SQLite Schema 和提交前故障钩子。
- gridarchive/vendor/sdk1.py：业务链使用的奇偶面域标量面积与交叠面积。
- gridarchive/vendor/sdk2.py：独立凸多边形端口，只提供凸形校验、面积和相交。

## 样例与检查

gridarchive.samples.populate(archive) 通过公开接口装入有限数据；build_legacy(path) 在调用方指定位置构造完整 SDK1 数据库。样例包含全部旧表、5 个几何修订、3 个观测版本、3 个固定任务和结果，以及网格和观测回执。重复装入不恢复旧 head、不新增回执或结果。path 应为持久数据库路径；调用方管理其目录。

原套件 tests/ 覆盖发布重开、回执重放和冲突、非法网格及观测拒绝、精确守恒、缺测、固定修订、替换、未运行状态、失败回滚和重开重试。几何核账包含手算、独立整数小格奇偶占用和两个独立端口的凸形交叉检查。没有外部服务或网络访问。

故障注入在 Archive(path, fault=callable) 设置。钩子接收真实事务事件，异常原样传播；grid.before_commit、field.before_commit、job.before_commit、result.after_insert、result.before_commit 均在提交前。事务捕获 BaseException 并回滚；结果失败保留上次完整发布。使用方式见 tests/test_publication.py。
