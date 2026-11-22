#!/usr/bin/env python3
"""段序放行戳端到端核证：同成败落戳、口径甲续装互证、半截整票回滚。

用独立临时库，不触碰工作区数据。运行：
  数据目录=<临时目录> python -I tests/test_段序戳.py
"""
import json
import os
import sys
import tempfile
import threading

后端根 = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, 后端根)

tmp = tempfile.mkdtemp(prefix="haoshu-stamp-test-")
os.environ["数据目录"] = tmp

import app.db as db  # noqa: E402

from app import seed  # noqa: E402
from app.services import 装载, 贯验  # noqa: E402
from app.modules import 段序放行戳 as 戳  # noqa: E402

夹具根 = os.path.join(后端根, "..", "fixtures")


def 读夹具(名: str) -> dict:
    with open(os.path.join(夹具根, f"{名}.json"), encoding="utf-8") as f:
        return json.load(f)


passed: list[str] = []
failed: list[str] = []


def 检查(名: str, cond: bool, 详情: str = "") -> None:
    (passed if cond else failed).append(名)
    print(f"[{'PASS' if cond else 'FAIL'}] {名}" + (f" — {详情}" if 详情 and not cond else ""))


seed.初始化库()
conn = db.连接()


def 戳数(批号: str) -> int:
    return conn.execute("SELECT COUNT(*) AS c FROM 段序放行戳 WHERE 批号=?", (批号,)).fetchone()["c"]


# --- 场景 0：写时段缺枢纽失败闭，也必须同成败落拒绝戳，且零增量 ---------------
甲 = 读夹具("序闸-甲-缺枢纽")
r = 装载.装一批(甲)
检查("甲-缺枢纽失败闭（拒绝/失败，零增量）", r["结果"] in ("拒绝", "失败"), r.get("说明", ""))
检查("甲-拒绝戳同成败落下", 戳数(甲["批次编号"]) == 1)
row = conn.execute("SELECT * FROM 段序放行戳 WHERE 批号=?", (甲["批次编号"],)).fetchone()
检查("甲-戳为拒绝且带原因", row["结果"] == "拒绝" and bool(row["拒绝原因"]))
检查("甲-失败批不进正式装载批次",
      conn.execute("SELECT 1 FROM 装载批次 WHERE 编号=?", (甲["批次编号"],)).fetchone() is None)
检查("甲-失败批无枢纽残留",
      conn.execute("SELECT 1 FROM 枢纽_号卡 WHERE 业务键=?", ("卡-13800030001",)).fetchone() is None)

# --- 场景 1：乱序可拓扑批成功，放行戳与正式表同成败、序不分叉 ------------------
乙 = 读夹具("序闸-乙-乱序可解")
r = 装载.装一批(乙)
检查("乙-乱序可解成功", r["结果"] == "成功", r.get("说明", ""))
检查("乙-原序确为乱序", r["装载序"]["原序"] == ["卫星", "链接", "枢纽"])
检查("乙-执行序按拓扑重排", r["装载序"]["执行序"] == ["枢纽", "链接", "卫星"])
检查("乙-成功批有且仅有一枚放行戳", 戳数(乙["批次编号"]) == 1)
row = conn.execute("SELECT * FROM 段序放行戳 WHERE 批号=?", (乙["批次编号"],)).fetchone()
检查("乙-戳为放行且双序非空带拓扑版本",
      row["结果"] == "放行" and json.loads(row["原序"]) and json.loads(row["执行序"])
      and row["拓扑版本"] == 戳.拓扑版本)
检查("乙-戳执行序与实落审计一致",
      json.loads(row["执行序"]) == json.loads(
          conn.execute("SELECT 执行序 FROM 装载序审计 WHERE 批次编号=? AND 结果='成功'",
                       (乙["批次编号"],)).fetchone()["执行序"]))
检查("乙-续装前置满足", 戳.允许续装(conn, 乙["批次编号"]) is True)

# 正常续装：有合法放行戳 → 可写
丙 = 读夹具("序闸-丙-续装补段")
r = 装载.装一批(丙)
检查("丙-有戳续装放行成功", r["结果"] == "成功", r.get("说明", ""))
检查("丙-续装批自身也落放行戳", 戳数(丙["批次编号"]) == 1)
检查("丙-续装对象已落且有父",
      conn.execute(
          "SELECT 1 FROM 卫星_号卡属性 s JOIN 枢纽_号卡 h ON h.哈希键=s.号卡哈希 "
          "WHERE h.业务键=? AND s.是否当前=1", ("卡-续装001",)).fetchone() is not None)

# --- 场景 2（再造一）：乱序首过后“无戳”续装卫星 —— 口径甲必须拒绝 -------------
无戳批 = "批-无戳-首装"
体首 = {
    "装载日": "2026-11-24",
    "批次编号": 无戳批,
    "枢纽": {"号卡": [{"业务键": "卡-无戳001"}]},
}
r = 装载.装一批(体首)
检查("无戳首装先成功", r["结果"] == "成功")
# 模拟缺陷态：对象已在正式表，戳被抹掉（闸成功而戳空）
conn.execute("DELETE FROM 段序放行戳 WHERE 批号=?", (无戳批,))
conn.commit()
检查("造态-正式表有对象但戳空",
      conn.execute("SELECT 1 FROM 装载批次 WHERE 编号=?", (无戳批,)).fetchone() is not None
      and 戳数(无戳批) == 0)

# 只读核证必须先把漂移报出来（对应口径乙“可写但核证失败”的可区分判据）
证 = 戳.核证(conn)
检查("核证-闸成功戳空判为不通过", 证["是否通过"] is False
      and any(无戳批 in x and "无放行戳" in x for x in 证["异常"]))

续 = {
    "装载日": "2026-11-24",
    "批次编号": "批-无戳-续装",
    "续装批号": 无戳批,
    "枢纽": {"号卡": [{"业务键": "卡-无戳002"}]},
    "卫星": {"号卡": [{"业务键": "卡-无戳002", "属性": {"状态": "在用"}}]},
}
前 = conn.total_changes
r = 装载.装一批(续)
检查("甲口径-无戳续装写闸拒绝", r["结果"] == "拒绝" and "续装前置不满足" in r["说明"], r.get("说明", ""))
检查("甲口径-拒绝批不进正式装载批次",
      conn.execute("SELECT 1 FROM 装载批次 WHERE 编号=?", ("批-无戳-续装",)).fetchone() is None)
检查("甲口径-续装枢纽未入正式表",
      conn.execute("SELECT 1 FROM 枢纽_号卡 WHERE 业务键=?", ("卡-无戳002",)).fetchone() is None)
检查("甲口径-续装批自身落拒绝戳（结论留痕）", 戳数("批-无戳-续装") == 1)
检查("甲口径-无父子对象未当前",
      conn.execute(
          "SELECT 1 FROM 卫星_号卡属性 s LEFT JOIN 枢纽_号卡 h ON h.哈希键=s.号卡哈希 "
          "WHERE h.哈希键 IS NULL AND s.是否当前=1").fetchone() is None)

# 对照：补齐放行戳后同载荷续装应成功，证明成败只由“戳”区分
conn.execute(
    "INSERT INTO 段序放行戳(批号,原序,执行序,拓扑版本,结果,拒绝原因,时刻) "
    "VALUES (?,?,?,?,?,'',?)",
    (无戳批, json.dumps(["枢纽"], ensure_ascii=False), json.dumps(["枢纽"], ensure_ascii=False),
     戳.拓扑版本, 戳.放行, seed.此刻()),
)
conn.commit()
检查("补戳后续装前置恢复", 戳.允许续装(conn, 无戳批) is True)
续["批次编号"] = "批-无戳-续装-补戳后"
r = 装载.装一批(续)
检查("补戳后续装成功（成败可区分）", r["结果"] == "成功", r.get("说明", ""))

# --- 场景 3（再造二）：首装与续装并发 + 半截失败，正式表不得有无父卫星 --------
并发基批 = "批-并发-首装"
体基 = {
    "装载日": "2026-11-25",
    "批次编号": 并发基批,
    "枢纽": {"号卡": [{"业务键": "卡-并发基001"}], "套餐": [{"业务键": "套-并发基001"}]},
}
r = 装载.装一批(体基)
检查("并发-首装基批成功", r["结果"] == "成功")

果: dict = {}


def 半截首装():
    # 卫星段抛错的首装：枢纽可能已落，必须整票回滚、零半截
    t = {
        "装载日": "2026-11-25",
        "批次编号": "批-并发-半截",
        "枢纽": {"号卡": [{"业务键": "卡-并发半截001"}]},
        "卫星": {"号卡": [{"业务键": "卡-并发半截001", "属性": {"炸": True}}]},
    }
    原开卫星 = 装载._开卫星

    def 炸开(*a, **kw):
        raise RuntimeError("注入:卫星段半截失败")

    装载._开卫星 = 炸开
    try:
        果["半截"] = 装载.装一批(t)
    finally:
        装载._开卫星 = 原开卫星


def 正常续装():
    t = {
        "装载日": "2026-11-25",
        "批次编号": "批-并发-续装",
        "续装批号": 并发基批,
        "枢纽": {"客户": [{"业务键": "客-并发续001"}]},
    }
    果["续装"] = 装载.装一批(t)


t1 = threading.Thread(target=半截首装)
t2 = threading.Thread(target=正常续装)
t1.start(); t2.start()
t1.join(15); t2.join(15)
检查("并发-半截首装报失败", 果.get("半截", {}).get("结果") == "失败")
检查("并发-半截残留为0（整票回滚）", 果.get("半截", {}).get("半截残留") == 0,
      str(果.get("半截")))
检查("并发-半截枢纽未残留",
      conn.execute("SELECT 1 FROM 枢纽_号卡 WHERE 业务键=?", ("卡-并发半截001",)).fetchone() is None)
检查("并发-有戳续装仍成功", 果.get("续装", {}).get("结果") == "成功", str(果.get("续装")))
检查("并发-正式表无无父当前卫星",
      conn.execute(
          "SELECT COUNT(*) AS c FROM 卫星_号卡属性 s LEFT JOIN 枢纽_号卡 h ON h.哈希键=s.号卡哈希 "
          "WHERE h.哈希键 IS NULL AND s.是否当前=1").fetchone()["c"] == 0)
# 订购卫星无链接父的半截：链接缺枢纽整票回滚
缺链 = {
    "装载日": "2026-11-25",
    "批次编号": "批-并发-无链卫星",
    "卫星": {"订购": [{"号卡业务键": "卡-不存在", "套餐业务键": "套-不存在",
                       "属性": {"状态": "有效"}}]},
}
r = 装载.装一批(缺链)
检查("无链卫星首装失败闭", r["结果"] == "失败")
检查("无链卫星未留无父当前",
      conn.execute(
          "SELECT COUNT(*) AS c FROM 卫星_订购属性 s LEFT JOIN 链接_号卡套餐 l ON l.哈希键=s.链接哈希 "
          "WHERE l.哈希键 IS NULL AND s.是否当前=1").fetchone()["c"] == 0)

# --- 场景 4：硬约束——戳序分叉禁止落库 ----------------------------------------
try:
    戳.落戳(conn, "批-非法分叉", {"原序": ["枢纽", "卫星"], "执行序": ["卫星", "枢纽"]}, 戳.放行)
    检查("分叉放行戳被拒", False)
except 戳.戳违例:
    检查("分叉放行戳被拒", True)
conn.rollback()
try:
    戳.落戳(conn, "批-空序", {"原序": [], "执行序": []}, 戳.放行)
    检查("空序放行戳被拒", False)
except 戳.戳违例:
    检查("空序放行戳被拒", True)
conn.rollback()

# --- 场景 5：只读接口与贯验协同 ------------------------------------------------
投影 = 戳.查戳(conn, 乙["批次编号"])
检查("只读-戳投影带口径与拓扑版本", 投影["口径"] == 戳.口径 and 投影["戳"][0]["拓扑版本"])
全程证 = 戳.核证(conn)
检查("只读-核证接口存在且可跑", isinstance(全程证["检项"], list) and len(全程证["检项"]) == 4)
贯 = 贯验.跑贯验()
戳检项名 = [x["名"] for x in 贯["检项"] if x["名"].startswith("段序戳·")]
检查("贯验-并入四个段序戳检项", len(戳检项名) == 4, str(戳检项名))
检查("贯验-段序戳核证口径回传", 贯["段序戳核证"]["口径"] == 戳.口径)

conn.close()

print(f"\n==== {len(passed)} passed / {len(failed)} failed ====")
if failed:
    print("FAILED:", *failed, sep="\n - ")
    sys.exit(1)
print("ALL GREEN")
