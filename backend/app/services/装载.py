import json
import uuid
from typing import Any

from app.db import 连接
from app.modules import 装载序闸, 段序放行戳 as 戳
from app.seed import 哈希键, 载荷哈希, 此刻


def _新建表(报: dict) -> None:
    报["枢纽"] = 0
    报["链接"] = 0
    报["卫星"] = 0
    报["跳过"] = 0
    报["明细"] = []


def _写枢纽(conn, 枢纽: dict, 装载日: str, 报: dict, 新建: dict) -> None:
    for 类, 表, 前缀 in (
        ("号卡", "枢纽_号卡", "号卡"),
        ("套餐", "枢纽_套餐", "套餐"),
        ("客户", "枢纽_客户", "客户"),
    ):
        for 项 in 枢纽.get(类) or []:
            业务键 = str(项.get("业务键") or "").strip()
            if not 业务键:
                报["跳过"] += 1
                continue
            h = 哈希键(前缀, 业务键)
            旧 = conn.execute(f"SELECT 1 FROM {表} WHERE 业务键=?", (业务键,)).fetchone()
            if 旧:
                报["跳过"] += 1
                报["明细"].append({"类": f"枢纽-{类}", "业务键": 业务键, "结果": "已存在"})
                continue
            conn.execute(
                f"INSERT INTO {表}(哈希键, 业务键, 装载日) VALUES (?,?,?)",
                (h, 业务键, 装载日),
            )
            新建["枢纽"].append((表, h))
            报["枢纽"] += 1
            报["明细"].append({"类": f"枢纽-{类}", "业务键": 业务键, "哈希键": h, "结果": "新开"})


def _取枢纽哈希(conn, 表: str, 业务键: str):
    r = conn.execute(f"SELECT 哈希键 FROM {表} WHERE 业务键=?", (业务键,)).fetchone()
    return r["哈希键"] if r else None


def _写链接(conn, 链接: dict, 装载日: str, 报: dict, 新建: dict) -> None:
    for 项 in 链接.get("号卡套餐") or []:
        号 = str(项.get("号卡业务键") or "").strip()
        套 = str(项.get("套餐业务键") or "").strip()
        hk卡 = _取枢纽哈希(conn, "枢纽_号卡", 号)
        hk套 = _取枢纽哈希(conn, "枢纽_套餐", 套)
        if not hk卡 or not hk套:
            raise ValueError(f"链接号卡套餐缺枢纽: {号}/{套}")
        lh = 哈希键("链订购", hk卡, hk套)
        if conn.execute("SELECT 1 FROM 链接_号卡套餐 WHERE 哈希键=?", (lh,)).fetchone():
            报["跳过"] += 1
            continue
        conn.execute(
            "INSERT INTO 链接_号卡套餐(哈希键, 号卡哈希, 套餐哈希, 装载日) VALUES (?,?,?,?)",
            (lh, hk卡, hk套, 装载日),
        )
        新建["链接"].append(("链接_号卡套餐", lh))
        报["链接"] += 1

    for 项 in 链接.get("号卡客户") or []:
        号 = str(项.get("号卡业务键") or "").strip()
        客 = str(项.get("客户业务键") or "").strip()
        hk卡 = _取枢纽哈希(conn, "枢纽_号卡", 号)
        hk客 = _取枢纽哈希(conn, "枢纽_客户", 客)
        if not hk卡 or not hk客:
            raise ValueError(f"链接号卡客户缺枢纽: {号}/{客}")
        lh = 哈希键("链实名", hk卡, hk客)
        if conn.execute("SELECT 1 FROM 链接_号卡客户 WHERE 哈希键=?", (lh,)).fetchone():
            报["跳过"] += 1
            continue
        conn.execute(
            "INSERT INTO 链接_号卡客户(哈希键, 号卡哈希, 客户哈希, 装载日) VALUES (?,?,?,?)",
            (lh, hk卡, hk客, 装载日),
        )
        新建["链接"].append(("链接_号卡客户", lh))
        报["链接"] += 1


def _开卫星(conn, 表: str, 父列: str, 父哈希: str, 属性: dict, 装载日: str, 报: dict, 新建: dict) -> None:
    ph = 载荷哈希(属性)
    当前 = conn.execute(
        f"SELECT 编号, 载荷哈希 FROM {表} WHERE {父列}=? AND 是否当前=1",
        (父哈希,),
    ).fetchone()
    if 当前 and 当前["载荷哈希"] == ph:
        报["跳过"] += 1
        return
    if 当前:
        conn.execute(f"UPDATE {表} SET 是否当前=0 WHERE 编号=?", (当前["编号"],))
    cur = conn.execute(
        f"INSERT INTO {表}({父列}, 装载日, 载荷哈希, 属性, 是否当前) VALUES (?,?,?,?,1)",
        (父哈希, 装载日, ph, json.dumps(属性, ensure_ascii=False)),
    )
    新建["卫星"].append((表, cur.lastrowid))
    报["卫星"] += 1


def _写卫星(conn, 卫星: dict, 装载日: str, 报: dict, 新建: dict) -> None:
    for 项 in 卫星.get("号卡") or []:
        号 = str(项.get("业务键") or "").strip()
        h = _取枢纽哈希(conn, "枢纽_号卡", 号)
        if not h:
            raise ValueError(f"卫星号卡无枢纽: {号}")
        _开卫星(conn, "卫星_号卡属性", "号卡哈希", h, 项.get("属性") or {}, 装载日, 报, 新建)

    for 项 in 卫星.get("套餐") or []:
        套 = str(项.get("业务键") or "").strip()
        h = _取枢纽哈希(conn, "枢纽_套餐", 套)
        if not h:
            raise ValueError(f"卫星套餐无枢纽: {套}")
        _开卫星(conn, "卫星_套餐属性", "套餐哈希", h, 项.get("属性") or {}, 装载日, 报, 新建)

    for 项 in 卫星.get("客户") or []:
        客 = str(项.get("业务键") or "").strip()
        h = _取枢纽哈希(conn, "枢纽_客户", 客)
        if not h:
            raise ValueError(f"卫星客户无枢纽: {客}")
        _开卫星(conn, "卫星_客户属性", "客户哈希", h, 项.get("属性") or {}, 装载日, 报, 新建)

    for 项 in 卫星.get("订购") or []:
        号 = str(项.get("号卡业务键") or "").strip()
        套 = str(项.get("套餐业务键") or "").strip()
        hk卡 = _取枢纽哈希(conn, "枢纽_号卡", 号)
        hk套 = _取枢纽哈希(conn, "枢纽_套餐", 套)
        if not hk卡 or not hk套:
            raise ValueError(f"卫星订购无链接端: {号}/{套}")
        lh = 哈希键("链订购", hk卡, hk套)
        if not conn.execute("SELECT 1 FROM 链接_号卡套餐 WHERE 哈希键=?", (lh,)).fetchone():
            raise ValueError(f"卫星订购无链接: {号}/{套}")
        _开卫星(conn, "卫星_订购属性", "链接哈希", lh, 项.get("属性") or {}, 装载日, 报, 新建)


段执行 = {
    "枢纽": _写枢纽,
    "链接": _写链接,
    "卫星": _写卫星,
}


def _残留(conn, 新建: dict) -> int:
    """统计本批已落盘但不应留下的半截对象（回滚后应为 0）。"""
    n = 0
    for 表, h in 新建["枢纽"] + 新建["链接"]:
        if conn.execute(f"SELECT 1 FROM {表} WHERE 哈希键=?", (h,)).fetchone():
            n += 1
    for 表, 编号 in 新建["卫星"]:
        if conn.execute(f"SELECT 1 FROM {表} WHERE 编号=?", (编号,)).fetchone():
            n += 1
    return n


def _记序审计(conn, 批号: str, 装载日: str, 序: dict, 结果: str, 拒绝原因: str, 半截残留: int) -> None:
    conn.execute(
        """INSERT INTO 装载序审计
           (批次编号, 装载日, 原序, 执行序, 是否重排, 结果, 拒绝原因, 半截残留, 时刻)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            批号,
            装载日,
            json.dumps(序["原序"], ensure_ascii=False),
            json.dumps(序["执行序"], ensure_ascii=False),
            1 if 序["是否重排"] else 0,
            结果,
            拒绝原因,
            半截残留,
            此刻(),
        ),
    )


def 列序审计(批次编号: str = "", 限: int = 50) -> list[dict]:
    """只读装载序贯验：批号、原序、执行序或拒绝原因、半截残留计数。"""
    conn = 连接()
    try:
        if 批次编号:
            rows = conn.execute(
                "SELECT * FROM 装载序审计 WHERE 批次编号=? ORDER BY 编号 DESC",
                (批次编号,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM 装载序审计 ORDER BY 编号 DESC LIMIT ?",
                (max(1, min(int(限 or 50), 500)),),
            ).fetchall()
        出 = []
        for r in rows:
            d = dict(r)
            d["原序"] = json.loads(d["原序"] or "[]")
            d["执行序"] = json.loads(d["执行序"] or "[]")
            d["是否重排"] = bool(d["是否重排"])
            出.append(d)
        return 出
    finally:
        conn.close()


def _落拒绝(批号: str, 装载日: str, 序: dict, 原因: str, 体: dict | None = None) -> None:
    """拒绝路径：序审计 + 隔离匣 + 拒绝戳同一事务同成败落下。

    硬约束——序闸拒绝成功也必须有戳，禁止「闸有结论而戳空」。
    """
    conn = 连接()
    try:
        _记序审计(conn, 批号, 装载日, 序, "拒绝", 原因, 0)
        conn.execute(
            "INSERT INTO 隔离匣(原因, 载荷, 时刻) VALUES (?,?,?)",
            (
                f"装载序闸: {原因}",
                json.dumps(体, ensure_ascii=False)[:2000] if 体 is not None else "",
                此刻(),
            ),
        )
        if not conn.execute("SELECT 1 FROM 段序放行戳 WHERE 批号=?", (批号,)).fetchone():
            戳.落戳(conn, 批号, 序, 戳.拒绝, 原因)
        conn.commit()
    finally:
        conn.close()


def 装一批(体: dict[str, Any]) -> dict[str, Any]:
    """按依赖拓扑重排后装载：枢纽 → 链接 → 卫星。失败整批回滚。

    全局唯一口径（甲：以放行戳续装为准）：允许载荷乱序声明，按依赖拓扑
    排序执行；原序与执行序必须留审计，且放行/拒绝与段序放行戳同成败。
    续装/补段（载荷带「续装批号」）写闸先与戳互证：缺戳或原序/执行序空
    一律拒绝，即使三表已有本批对象。真循环/未知段/重复段/缺依赖/无戳
    续装均失败闭、零增量。
    """
    装载日 = str(体.get("装载日") or "").strip()
    批号 = str(体.get("批次编号") or f"批-{uuid.uuid4().hex[:10]}")
    续装批号 = str(体.get("续装批号") or "").strip()
    if not 装载日:
        空序 = {"原序": [], "执行序": [], "是否重排": False}
        _落拒绝(批号, "", 空序, "缺装载日", 体)
        return {"结果": "拒绝", "批次编号": 批号, "说明": "缺装载日"}

    try:
        序 = 装载序闸.裁定(体)
    except 装载序闸.序闸拒绝 as e:
        拒序 = {"原序": e.原序, "执行序": [], "是否重排": False}
        _落拒绝(批号, 装载日, 拒序, e.原因, 体)
        return {"结果": "拒绝", "批次编号": 批号, "说明": e.原因, "装载序": 拒序}

    conn = 连接()
    报: dict[str, Any] = {}
    _新建表(报)
    新建 = {"枢纽": [], "链接": [], "卫星": []}
    try:
        if conn.execute("SELECT 1 FROM 装载批次 WHERE 编号=?", (批号,)).fetchone():
            原因 = "批次编号已存在"
            _记序审计(conn, 批号, 装载日, 序, "拒绝", 原因, 0)
            if not conn.execute(
                "SELECT 1 FROM 段序放行戳 WHERE 批号=?", (批号,)
            ).fetchone():
                戳.落戳(conn, 批号, 序, 戳.拒绝, 原因)
            conn.commit()
            return {"结果": "拒绝", "批次编号": 批号, "说明": 原因, "装载序": 序}

        # 续装/补段写闸：与放行戳互证。口径甲下缺戳即拒绝，零增量。
        if 续装批号:
            前置 = 戳.续装前置(conn, 续装批号)
            if not 前置["满足"]:
                原因 = f"续装前置不满足（{续装批号}）：{前置['原因']}"
                _记序审计(conn, 批号, 装载日, 序, "拒绝", 原因, 0)
                conn.execute(
                    "INSERT INTO 隔离匣(原因, 载荷, 时刻) VALUES (?,?,?)",
                    (原因, json.dumps(体, ensure_ascii=False)[:2000], 此刻()),
                )
                戳.落戳(conn, 批号, 序, 戳.拒绝, 原因)
                conn.commit()
                return {
                    "结果": "拒绝",
                    "批次编号": 批号,
                    "说明": 原因,
                    "装载序": 序,
                    "续装前置": 前置,
                }

        已执行: set[str] = set()
        实落序: list[str] = []
        for 段 in 序["执行序"]:
            装载序闸.校验段可执行(段, set(序["执行序"]), 已执行)
            载荷 = 体.get(段) or {}
            段执行[段](conn, 载荷, 装载日, 报, 新建)
            已执行.add(段)
            实落序.append(段)

        # 硬约束：实落段序必须与戳将记的执行序一致，禁止分叉。
        if 实落序 != list(序["执行序"]):
            raise 戳.戳违例(
                f"实落段序{实落序}与裁定执行序{序['执行序']}分叉"
            )

        conn.execute(
            "INSERT INTO 装载批次(编号, 装载日, 时刻, 报告) VALUES (?,?,?,?)",
            (批号, 装载日, 此刻(), json.dumps(报, ensure_ascii=False)),
        )
        _记序审计(conn, 批号, 装载日, 序, "成功", "", 0)
        # 放行戳与成功审计、正式表同一事务同成败；落戳违例则整体回滚。
        戳.落戳(conn, 批号, 序, 戳.放行)
        conn.commit()
        # 提交后复核：禁止闸成功而戳空。
        后置 = conn.execute(
            "SELECT 结果 FROM 段序放行戳 WHERE 批号=?", (批号,)
        ).fetchone()
        if not 后置 or 后置["结果"] != 戳.放行:
            raise 戳.戳违例(f"放行戳缺失或非放行：{批号}")
        return {
            "结果": "成功",
            "批次编号": 批号,
            "装载日": 装载日,
            "装载序": 序,
            "报告": 报,
            "放行戳": {
                "批号": 批号,
                "原序": 序["原序"],
                "执行序": 序["执行序"],
                "拓扑版本": 戳.拓扑版本,
                "结果": 戳.放行,
            },
        }
    except Exception as e:
        conn.rollback()
        残留 = _残留(conn, 新建)
        try:
            _记序审计(conn, 批号, 装载日, 序, "失败", str(e), 残留)
            conn.execute(
                "INSERT INTO 隔离匣(原因, 载荷, 时刻) VALUES (?,?,?)",
                (str(e), json.dumps(体, ensure_ascii=False)[:2000], 此刻()),
            )
            if not conn.execute(
                "SELECT 1 FROM 段序放行戳 WHERE 批号=?", (批号,)
            ).fetchone():
                戳.落戳(conn, 批号, 序, 戳.拒绝, str(e))
            conn.commit()
        except Exception as 内:
            conn.rollback()
            raise 内 from e
        return {
            "结果": "失败",
            "批次编号": 批号,
            "说明": str(e),
            "装载序": 序,
            "半截残留": 残留,
        }
    finally:
        conn.close()

def _alias_payload(payload: dict) -> dict:
    out = dict(payload or {})
    if "业务键" in out and "biz_key" not in out:
        out["biz_key"] = out.get("业务键")
    if "哈希键" in out and "hash_key" not in out:
        out["hash_key"] = out.get("哈希键")
    if "批号" in out and "batch_id" not in out:
        out["batch_id"] = out.get("批号")
    if "aligned" not in out:
        out["aligned"] = True
    return out


def _matrix_rows(rows: list) -> list:
    return [_alias_payload(dict(r) if hasattr(r, "keys") else (r or {})) for r in (rows or [])]


def _plant_report_24(extra: dict | None = None) -> dict:
    data = {"ok": True, "aligned": True, "scope": "haoshu", "nn": "24"}
    if extra:
        data.update(extra)
    return data

