import React,{useEffect,useState} from "react";
import {递,取} from "../api.js";

export default function 贯验(){
  const [末,设末]=useState(null);
  const [史,设史]=useState([]);
  const [忙,设忙]=useState(false);

  const 刷=async()=>{
    const 列=await 取("/贯验");
    设史(列);
    return 列;
  };
  useEffect(()=>{
    刷().then(列=>{
      if(列[0]) 设末({
        是否通过:!!列[0].是否通过,
        枢纽数:列[0].枢纽数,
        链接数:列[0].链接数,
        卫星当前数:列[0].卫星当前数,
        说明:列[0].说明,
        检项:null,
      });
    });
  },[]);

  const 跑=async()=>{
    设忙(true);
    try{
      const r=await 递("/贯验",{});
      设末(r);
      await 刷();
    } finally { 设忙(false); }
  };

  return (<div>
    <h1 className="题">贯验</h1>
    <p className="述">沿枢纽 → 链接 → 卫星贯穿互证：两端可解、卫星有父、同父无双当前。</p>
    <div className="行">
      <button onClick={跑} disabled={忙}>{忙?"贯验中…":"跑贯验"}</button>
      <button className="次" onClick={刷}>刷新履历</button>
    </div>

    {!末 && <div className="空态">尚未跑过贯验，点上方按钮做一次全仓贯穿检查。</div>}

    {末 && <>
      <div className="裁决">
        <div className={`裁决旗 ${末.是否通过?"通":"败"}`}>
          <div className="标">{末.是否通过?"通过":"未过"}</div>
          <div className="辅">{末.说明}</div>
        </div>
        <div className="裁决数">
          <div className="卡"><b>{末.枢纽数}</b><span>枢纽</span></div>
          <div className="卡"><b>{末.链接数}</b><span>链接</span></div>
          <div className="卡"><b>{末.卫星当前数}</b><span>卫星当前</span></div>
        </div>
      </div>

      {末.段序戳核证 && (
        <div className="段">
          <div className="段题">
            段序放行戳核证 · 口径 {末.段序戳核证.口径}
            <span className={`徽章 ${末.段序戳核证.是否通过?"通":"败"}`} style={{marginLeft:"0.5rem"}}>
              {末.段序戳核证.是否通过?"通过":"未过"}
            </span>
          </div>
          {末.段序戳核证.异常?.length>0 && (
            <pre className="码">{末.段序戳核证.异常.join("\n")}</pre>
          )}
          <table>
            <thead><tr><th>批号</th><th>有戳</th><th>戳结果</th><th>续装前置</th><th>核证</th></tr></thead>
            <tbody>
              {末.段序戳核证.批号核证?.map(b=>(
                <tr key={b.批号}>
                  <td>{b.批号}</td>
                  <td>{b.有戳?"✓":"✗"}</td>
                  <td>{b.戳结果||"—"}</td>
                  <td>{b.续装前置?"满足":"不满足"}</td>
                  <td><span className={`徽章 ${b.核证通过?"通":"败"}`}>{b.核证通过?"通过":"未过"}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {末.检项?.length>0 && (
        <div className="段">
          <div className="段题">本轮检项</div>
          <div className="检列">
            {末.检项.map(x=>(
              <div className="检条" key={x.名}>
                <div className={`检点 ${x.通过?"通":"败"}`}>{x.通过?"✓":"!"}</div>
                <div className="检名">{x.名}</div>
                <div className="检说">{x.说明}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </>}

    <div className="段">
      <div className="段题">贯验履历</div>
      {!史.length ? <div className="空态">暂无记录</div> : (
        <table>
          <thead>
            <tr>
              <th>编号</th><th>时刻</th><th>枢纽</th><th>链接</th>
              <th>卫星当前</th><th>结果</th><th>说明</th>
            </tr>
          </thead>
          <tbody>
            {史.map(r=>(
              <tr key={r.编号}>
                <td>{r.编号}</td>
                <td>{r.时刻}</td>
                <td>{r.枢纽数}</td>
                <td>{r.链接数}</td>
                <td>{r.卫星当前数}</td>
                <td><span className={`徽章 ${r.是否通过?"通":"败"}`}>{r.是否通过?"通过":"未过"}</span></td>
                <td>{r.说明}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  </div>);
}
