状态 = "已落盘"

说明 = (
    "任一段失败整票回滚（connection.rollback），回滚后按本批新建清单复核"
    "半截残留必须为 0；失败结论与拒绝戳同事务落审计/隔离匣，正式表不留"
    "无父链接、无父当前卫星。"
)


def 复核残留(conn, 新建: dict) -> int:
    """回滚后调用：统计本批新建对象残留，正常应为 0。"""
    n = 0
    for 表, h in 新建.get("枢纽", []) + 新建.get("链接", []):
        if conn.execute(f"SELECT 1 FROM {表} WHERE 哈希键=?", (h,)).fetchone():
            n += 1
    for 表, 编号 in 新建.get("卫星", []):
        if conn.execute(f"SELECT 1 FROM {表} WHERE 编号=?", (编号,)).fetchone():
            n += 1
    return n

