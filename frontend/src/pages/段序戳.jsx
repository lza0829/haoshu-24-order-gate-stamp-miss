import React, { useEffect, useState } from "react";
import { 取 } from "../api.js";

export default function 段序戳() {
  const [投影, 设投影] = useState(null);
  const [核证, 设核证] = useState(null);
  const [err, 设err] = useState("");
  const reload = async () => {
    设err("");
    try {
      const [p, v] = await Promise.all([
        取("/贯验/段序戳"),
        取("/贯验/段序戳/核证"),
      ]);
      设投影(p);
      设核证(v);
    } catch (e) {
      设err(String(e.message || e));
    }
  };
  useEffect(() => { reload(); }, []);

  return (
    <div>
      <h1 className="题">段序放行戳</h1>
      <p className="述">
        序闸放行/拒绝与放行戳同成败：批号、原序、执行序、拓扑版本、结果或拒绝原因。
        全局唯一口径由写闸强制，续装/补段先与戳互证。
      </p>
      <div className="行">
        <button className="次" onClick={reload}>刷新</button>
      </div>
      {err && <pre className="码">{err}</pre>}

      {核证 && (
        <div className="段">
          <div className="段题">段序戳核证（只读）</div>
          <div className="装载顶">
            <span className={`徽章 ${核证.是否通过 ? "通" : "败"}`}>
              {核证.是否通过 ? "核证通过" : "核证未过"}
            </span>
            <span className="日">口径：{核证.口径}</span>
            <span className="日">拓扑版本：{核证.拓扑版本}</span>
            <span className="日">戳 {核证.戳数} 枚 · 正式批 {核证.正式批数} 个</span>
          </div>
          <div className="检列">
            {核证.检项.map((x) => (
              <div className="检条" key={x.名}>
                <div className={`检点 ${x.通过 ? "通" : "败"}`}>{x.通过 ? "✓" : "!"}</div>
                <div className="检名">{x.名}</div>
                <div className="检说">{x.说明}</div>
              </div>
            ))}
          </div>
          {!!核证.异常.length && (
            <pre className="码" style={{ marginTop: "0.5rem" }}>
              {核证.异常.join("\n")}
            </pre>
          )}
        </div>
      )}

      <div className="段">
        <div className="段题">放行戳投影</div>
        {!投影?.戳?.length ? (
          <div className="空态">暂无放行戳</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>批号</th><th>结果</th><th>原序</th><th>执行序</th>
                <th>拓扑版本</th><th>拒绝原因</th><th>续装前置</th><th>时刻</th>
              </tr>
            </thead>
            <tbody>
              {投影.戳.map((s) => (
                <tr key={s.编号}>
                  <td>{s.批号}</td>
                  <td>
                    <span className={`徽章 ${s.结果 === "放行" ? "通" : "败"}`}>{s.结果}</span>
                  </td>
                  <td className="哈希">{(s.原序 || []).join(" → ") || "—"}</td>
                  <td className="哈希">{(s.执行序 || []).join(" → ") || "—"}</td>
                  <td>{s.拓扑版本 || "—"}</td>
                  <td>{s.拒绝原因 || "—"}</td>
                  <td>
                    <span className={`徽章 ${s.续装前置 ? "通" : "淡"}`}>
                      {s.续装前置 ? "满足" : "不满足"}
                    </span>
                  </td>
                  <td>{s.时刻}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {核证?.批号核证?.length > 0 && (
        <div className="段">
          <div className="段题">逐批号核证</div>
          <table>
            <thead>
              <tr><th>批号</th><th>有戳</th><th>戳结果</th><th>执行序</th><th>续装前置</th><th>核证</th></tr>
            </thead>
            <tbody>
              {核证.批号核证.map((b) => (
                <tr key={b.批号}>
                  <td>{b.批号}</td>
                  <td>{b.有戳 ? "✓" : "✗ 戳空"}</td>
                  <td>{b.戳结果 || "—"}</td>
                  <td className="哈希">{(b.执行序 || []).join(" → ") || "—"}</td>
                  <td>{b.续装前置 ? "满足" : "不满足"}</td>
                  <td>
                    <span className={`徽章 ${b.核证通过 ? "通" : "败"}`}>
                      {b.核证通过 ? "通过" : "未过"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
