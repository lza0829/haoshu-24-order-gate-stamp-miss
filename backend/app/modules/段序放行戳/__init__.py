"""段序放行戳（口径甲：以放行戳续装为准）。

全局唯一口径：序闸放行或拒绝成功，必须与放行戳同成败落下。续装/补段
写闸与戳互证——缺戳、或戳中原序/执行序为空、或非「放行」戳，一律拒绝
续装，即使三表已落本批对象。

硬约束（在本模块与装载编排中共同强制）：
  1. 禁止闸成功而戳空：每个成功批必有一枚「放行」戳，每次拒绝必有一枚「拒绝」戳；
  2. 禁止戳执行序与实落段序分叉：戳的执行序须与装载序审计成功行一致且拓扑合法；
  3. 禁止无戳续装插入无父子对象：续装前置不满足时写闸直接拒绝，整票零增量。

口径乙（以三表已落为准）不在本系统贯彻；核证接口会把「三表已落但无放行
戳」判为漂移异常，使两口径下「乱序首过后无戳续装卫星」的成败可区分：
甲写闸拒绝（本实现），乙可写但段序戳核证失败。
"""

import json

from app.seed import 此刻
from app.modules.装载序闸 import 段名, 依赖

状态 = "已落盘"
口径 = "甲-以放行戳续装为准"
拓扑版本 = "topo-hub-link-sat/v1"

放行 = "放行"
拒绝 = "拒绝"
_合法结果 = (放行, 拒绝)


class 戳违例(Exception):
    """放行戳自洽性被破坏（禁止以此状态落库）。"""


def _dumps(序) -> str:
    return json.dumps(list(序 or []), ensure_ascii=False)


def _loads(s) -> list[str]:
    try:
        v = json.loads(s or "[]")
        return [str(x) for x in v] if isinstance(v, list) else []
    except (TypeError, ValueError):
        return []


def _拓扑合法(执行序: list[str]) -> bool:
    """执行序必须是段名的无重复子集，且每个段的依赖段先于它出现。"""
    if len(执行序) != len(set(执行序)):
        return False
    已见: set[str] = set()
    for 段 in 执行序:
        if 段 not in 段名:
            return False
        for 前置 in 依赖[段]:
            if 前置 in 执行序 and 前置 not in 已见:
                return False
        已见.add(段)
    return True


def 落戳(conn, 批号: str, 序: dict, 结果: str, 拒绝原因: str = "") -> None:
    """与闸裁决同成败落放行戳。非法状态直接抛 戳违例，禁止落半截戳。"""
    批号 = str(批号 or "").strip()
    if not 批号:
        raise 戳违例("放行戳批号为空")
    if 结果 not in _合法结果:
        raise 戳违例(f"放行戳结果非法: {结果!r}")

    原序 = list((序 or {}).get("原序") or [])
    执行序 = list((序 or {}).get("执行序") or [])

    if 结果 == 放行:
        if not 原序 or not 执行序:
            raise 戳违例("放行戳原序/执行序不得为空")
        if set(原序) != set(执行序):
            raise 戳违例("放行戳原序段集与执行序段集分叉")
        if not _拓扑合法(执行序):
            raise 戳违例("放行戳执行序不满足枢纽→链接→卫星拓扑")
        if 拒绝原因:
            raise 戳违例("放行戳不得带拒绝原因")
    else:
        if not str(拒绝原因 or "").strip():
            raise 戳违例("拒绝戳必须带拒绝原因")

    conn.execute(
        """INSERT INTO 段序放行戳(批号, 原序, 执行序, 拓扑版本, 结果, 拒绝原因, 时刻)
           VALUES (?,?,?,?,?,?,?)""",
        (批号, _dumps(原序), _dumps(执行序), 拓扑版本, 结果, str(拒绝原因 or ""), 此刻()),
    )


def 续装前置(conn, 批号: str) -> dict:
    """口径甲续装/补段前置条件核证。缺戳或原序/执行序空即不满足。"""
    批号 = str(批号 or "").strip()
    if not 批号:
        return {"满足": False, "原因": "续装批号为空", "口径": 口径}
    row = conn.execute(
        "SELECT * FROM 段序放行戳 WHERE 批号=?", (批号,)
    ).fetchone()
    if not row:
        return {
            "满足": False,
            "原因": "缺放行戳：即使三表已落本批对象，口径甲也拒绝无戳续装",
            "口径": 口径,
        }
    if row["结果"] != 放行:
        return {
            "满足": False,
            "原因": f"前批非放行戳（{row['结果']}:{row['拒绝原因']}），不得续装",
            "口径": 口径,
        }
    原序 = _loads(row["原序"])
    执行序 = _loads(row["执行序"])
    if not 原序 or not 执行序:
        return {"满足": False, "原因": "放行戳原序/执行序为空", "口径": 口径}
    if not _拓扑合法(执行序) or set(原序) != set(执行序):
        return {"满足": False, "原因": "放行戳段序不自洽或拓扑分叉", "口径": 口径}
    return {
        "满足": True,
        "原因": "",
        "口径": 口径,
        "拓扑版本": row["拓扑版本"],
        "原序": 原序,
        "执行序": 执行序,
    }


def 允许续装(conn, 批号: str) -> bool:
    return 续装前置(conn, 批号)["满足"]


def 查戳(conn, 批号: str | None = None) -> dict:
    """只读：放行戳投影，并附全局口径与每枚戳的续装前置判定。"""
    if 批号:
        rows = conn.execute(
            "SELECT * FROM 段序放行戳 WHERE 批号=? ORDER BY 编号", (批号,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM 段序放行戳 ORDER BY 编号 DESC LIMIT 50"
        ).fetchall()
    戳 = []
    for r in rows:
        d = dict(r)
        d["原序"] = _loads(d.get("原序"))
        d["执行序"] = _loads(d.get("执行序"))
        d["续装前置"] = 续装前置(conn, d["批号"])["满足"]
        戳.append(d)
    return {"口径": 口径, "拓扑版本": 拓扑版本, "戳": 戳, "续装前置": False}


def _戳自检(row) -> list[str]:
    问题: list[str] = []
    批号 = row["批号"]
    原序 = _loads(row["原序"])
    执行序 = _loads(row["执行序"])
    if row["结果"] not in _合法结果:
        问题.append(f"{批号}:戳结果非法({row['结果']})")
    if row["结果"] == 放行:
        if not 原序 or not 执行序:
            问题.append(f"{批号}:放行戳原序/执行序为空")
        if set(原序) != set(执行序):
            问题.append(f"{批号}:原序段集与执行序分叉")
        if not _拓扑合法(执行序):
            问题.append(f"{批号}:执行序违反枢纽→链接→卫星拓扑")
        if row["拒绝原因"]:
            问题.append(f"{批号}:放行戳带拒绝原因")
    if row["结果"] == 拒绝 and not row["拒绝原因"]:
        问题.append(f"{批号}:拒绝戳缺拒绝原因")
    if not row["拓扑版本"]:
        问题.append(f"{批号}:缺拓扑版本")
    return 问题


def _孤儿当前(conn) -> list[str]:
    问题: list[str] = []
    for 表, 列, 父表 in (
        ("卫星_号卡属性", "号卡哈希", "枢纽_号卡"),
        ("卫星_套餐属性", "套餐哈希", "枢纽_套餐"),
        ("卫星_客户属性", "客户哈希", "枢纽_客户"),
        ("卫星_订购属性", "链接哈希", "链接_号卡套餐"),
    ):
        for r in conn.execute(
            f"SELECT {列} AS p FROM {表} WHERE 是否当前=1"
        ):
            if not conn.execute(
                f"SELECT 1 FROM {父表} WHERE 哈希键=?", (r["p"],)
            ).fetchone():
                问题.append(f"{表}:{r['p']}")
    return 问题


def 核证(conn) -> dict:
    """只读段序戳核证（基线所无的新接口）。

    从戳投影、装载批次/序审计、三表当前对象三方互证，输出逐批核证与
    全局检项；口径甲下「三表已落但无放行戳」属漂移异常，整项不通过。
    """
    戳行 = [dict(r) for r in conn.execute("SELECT * FROM 段序放行戳 ORDER BY 编号")]
    戳映射 = {r["批号"]: r for r in 戳行}

    戳问题: list[str] = []
    for r in 戳行:
        戳问题.extend(_戳自检(r))

    # 正式表已落批（装载批次）与成功序审计，必须各有一枚自洽放行戳
    漂移: list[str] = []
    分叉: list[str] = []
    批次行 = [dict(r) for r in conn.execute("SELECT 编号 FROM 装载批次")]
    for b in 批次行:
        批 = b["编号"]
        s = 戳映射.get(批)
        if not s:
            漂移.append(f"{批}:正式表已落但无放行戳（闸成功而戳空）")
            continue
        if s["结果"] != 放行:
            漂移.append(f"{批}:正式表已落但戳为{s['结果']}")
            continue
        for a in conn.execute(
            "SELECT 原序, 执行序 FROM 装载序审计 WHERE 批次编号=? AND 结果='成功'",
            (批,),
        ):
            if _loads(a["执行序"]) != _loads(s["执行序"]):
                分叉.append(f"{批}:戳执行序与实落审计段序分叉")
            if _loads(a["原序"]) != _loads(s["原序"]):
                分叉.append(f"{批}:戳原序与审计原序分叉")

    成功无戳: list[str] = []
    for r in conn.execute(
        "SELECT DISTINCT 批次编号 FROM 装载序审计 WHERE 结果='成功'"
    ):
        批 = r["批次编号"]
        s = 戳映射.get(批)
        if not s or s["结果"] != 放行:
            成功无戳.append(f"{批}:序审计成功但无放行戳")

    孤儿 = [f"无父当前卫星:{x}" for x in _孤儿当前(conn)]

    逐批 = []
    for b in 批次行:
        批 = b["编号"]
        s = 戳映射.get(批)
        逐批.append(
            {
                "批号": 批,
                "有戳": s is not None,
                "戳结果": s["结果"] if s else None,
                "原序": _loads(s["原序"]) if s else [],
                "执行序": _loads(s["执行序"]) if s else [],
                "拓扑版本": s["拓扑版本"] if s else "",
                "续装前置": 允许续装(conn, 批),
                "核证通过": (
                    s is not None
                    and s["结果"] == 放行
                    and not _戳自检(s)
                    and not any(x.startswith(批 + ":") for x in 分叉)
                ),
            }
        )

    检项 = [
        {
            "名": "放行戳自洽",
            "通过": not 戳问题,
            "说明": "全部戳原序/执行序/拓扑版本/结果自洽" if not 戳问题 else "；".join(戳问题[:6]),
        },
        {
            "名": "闸成功必有戳",
            "通过": not 漂移 and not 成功无戳,
            "说明": (
                "正式表成功批均有放行戳，无闸成功戳空"
                if not 漂移 and not 成功无戳
                else "；".join((漂移 + 成功无戳)[:6])
            ),
        },
        {
            "名": "戳序与实落序一致",
            "通过": not 分叉,
            "说明": "戳执行序与装载序审计成功行一致" if not 分叉 else "；".join(分叉[:6]),
        },
        {
            "名": "无无父当前卫星",
            "通过": not 孤儿,
            "说明": "当前卫星均挂到合法父键" if not 孤儿 else "；".join(孤儿[:6]),
        },
    ]
    异常 = 戳问题 + 漂移 + 成功无戳 + 分叉 + 孤儿
    return {
        "口径": 口径,
        "拓扑版本": 拓扑版本,
        "是否通过": not 异常,
        "异常": 异常,
        "检项": 检项,
        "批号核证": 逐批,
        "戳数": len(戳行),
        "正式批数": len(批次行),
    }
