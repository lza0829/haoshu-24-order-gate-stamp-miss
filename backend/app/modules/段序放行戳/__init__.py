状态 = "半截"


def 查戳(conn, 批号: str | None = None) -> dict:
    rows = []
    try:
        if 批号:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 段序放行戳 WHERE 批号=?", (批号,)
            )]
        else:
            rows = [dict(r) for r in conn.execute(
                "SELECT * FROM 段序放行戳 ORDER BY 编号 DESC LIMIT 50"
            )]
    except Exception:
        rows = []
    return {"戳": rows, "续装前置": False}


def 允许续装(_conn, _批号: str) -> bool:
    return True
