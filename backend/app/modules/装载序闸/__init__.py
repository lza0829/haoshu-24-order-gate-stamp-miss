段名 = ("枢纽", "链接", "卫星")

依赖 = {
    "枢纽": (),
    "链接": ("枢纽",),
    "卫星": ("枢纽", "链接"),
}


class 序闸拒绝(Exception):
    """装载序无法裁定（未知段/重复段/真循环等）。"""

    def __init__(self, 原因: str, 原序=None):
        super().__init__(原因)
        self.原因 = 原因
        self.原序 = list(原序 or [])


def 段有料(载荷: dict, 段: str) -> bool:
    """该段是否承载了待装载对象。"""
    值 = (载荷 or {}).get(段)
    if not 值:
        return False
    if isinstance(值, dict):
        return any(bool(x) for x in 值.values())
    if isinstance(值, (list, tuple)):
        return any(bool(x) for x in 值)
    return bool(值)


def 归一原序(载荷: dict) -> list[str]:
    """取载荷声明的原始段序。

    优先读显式 `段序`；否则按载荷键出现顺序识别。显式声明中未知段或
    重复段直接拒绝闭。任何有料但未声明的段，按枢纽→链接→卫星补到末尾，
    避免静默丢段。
    """
    声明 = (载荷 or {}).get("段序") if isinstance(载荷, dict) else None
    原序: list[str] = []
    if 声明:
        if not isinstance(声明, (list, tuple)):
            raise 序闸拒绝("段序必须是数组")
        for 项 in 声明:
            段 = str(项 or "").strip()
            if not 段:
                continue
            if 段 not in 段名:
                raise 序闸拒绝(f"段序含未知段: {段}", 原序)
            if 段 in 原序:
                raise 序闸拒绝(f"段序重复: {段}", 原序)
            原序.append(段)
    elif isinstance(载荷, dict):
        for 键 in 载荷.keys():
            if 键 in 段名 and 键 not in 原序:
                原序.append(键)

    for 段 in 段名:
        if 段 not in 原序 and 段有料(载荷, 段):
            原序.append(段)
    return 原序


def 拓扑排序(节点: list[str]) -> list[str]:
    """按依赖对参与段做 Kahn 拓扑排序；成环则拒绝闭。"""
    节点集 = set(节点)
    入度 = {n: 0 for n in 节点集}
    后继 = {n: set() for n in 节点集}
    for n in 节点集:
        for 前置 in 依赖[n]:
            if 前置 in 节点集:
                后继[前置].add(n)
                入度[n] += 1

    就绪 = sorted([n for n in 节点集 if 入度[n] == 0], key=段名.index)
    执行序: list[str] = []
    while 就绪:
        n = 就绪.pop(0)
        执行序.append(n)
        for m in sorted(后继[n], key=段名.index):
            入度[m] -= 1
            if 入度[m] == 0:
                就绪.append(m)
                就绪.sort(key=段名.index)

    if len(执行序) != len(节点集):
        raise 序闸拒绝("依赖拓扑成环，无法裁定装载序", 节点)
    return 执行序


def 裁定(载荷: dict) -> dict:
    """裁定本批原序、执行序与是否重排。"""
    原序 = 归一原序(载荷)
    执行序 = 拓扑排序(原序)
    return {
        "原序": 原序,
        "执行序": 执行序,
        "是否重排": 原序 != 执行序,
    }


def 校验段可执行(段: str, 参与段: set[str], 已执行: set[str]) -> None:
    """各段写闸：依赖段必须在本批已执行。"""
    for 前置 in 依赖[段]:
        if 前置 in 参与段 and 前置 not in 已执行:
            raise 序闸拒绝(f"装载序闸: {段} 先于依赖段 {前置} 执行")
