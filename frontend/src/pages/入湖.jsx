import React,{useEffect,useState} from "react";
import {递,取} from "../api.js";

export default function 入湖(){
  const [报,设报]=useState(null);
  const [忙,设忙]=useState("");
  const [序录,设序录]=useState([]);

  const 刷序=async()=>{
    try{ const r=await 取("/装载序贯验?限=20"); 设序录(r.记录||[]); }
    catch(e){ 设序录([]); }
  };
  useEffect(()=>{刷序();},[]);

  const 灌=async (名)=>{
    设忙(名);
    try{ 设报(await 递("/装载/夹具?名="+encodeURIComponent(名),{})); }
    catch(e){ 设报({结果:"失败",说明:String(e.message||e)}); }
    finally{ 设忙(""); await 刷序(); }
  };

  const 报数=报?.报告||{};
  const 明细=报数.明细||[];
  const 序=报?.装载序;

  return (<div>
    <h1 className="题">入湖</h1>
    <p className="述">按依赖拓扑重排装载：枢纽 → 链接 → 卫星。允许载荷乱序声明，原序 ≠ 执行序 时留审计；缺依赖或真循环整批失败闭、零增量。</p>
    <div className="行">
      <button onClick={()=>灌("号卡套餐样例")} disabled={!!忙}>
        {忙==="号卡套餐样例"?"灌入中…":"灌入号卡套餐样例"}
      </button>
      <button className="次" onClick={()=>灌("套餐升档样例")} disabled={!!忙}>
        {忙==="套餐升档样例"?"灌入中…":"灌入套餐升档（卫星开版）"}
      </button>
      <button className="次" onClick={()=>灌("序闸-乙-乱序可解")} disabled={!!忙}>
        {忙==="序闸-乙-乱序可解"?"灌入中…":"灌入序闸乙（乱序可解）"}
      </button>
      <button className="次" onClick={()=>灌("序闸-甲-缺枢纽")} disabled={!!忙}>
        {忙==="序闸-甲-缺枢纽"?"灌入中…":"灌入序闸甲（缺枢纽）"}
      </button>
    </div>

    {!报 && <div className="空态">尚未装载。先灌样例，再到枢纽 / 链接 / 卫星查看落库。</div>}

    {报 && (
      <div className="装载报">
        <div className="装载顶">
          <span className={`徽章 ${报.结果==="成功"?"通":"败"}`}>{报.结果||"完成"}</span>
          {报.批次编号 && <span className="批">{报.批次编号}</span>}
          {报.装载日 && <span className="日">装载日 {报.装载日}</span>}
          {报.说明 && <span className="日">{报.说明}</span>}
          {typeof 报.半截残留==="number" && 报.半截残留>0 && <span className="徽章 败">半截残留 {报.半截残留}</span>}
        </div>
        {序 && (
          <div className="装载序">
            <span className="日">原序</span>
            <span className="哈希">{(序.原序||[]).join(" → ")||"—"}</span>
            <span className="日">执行序</span>
            <span className="哈希">{(序.执行序||[]).join(" → ")||"—"}</span>
            <span className={`徽章 ${序.是否重排?"败":"淡"}`}>{序.是否重排?"已重排":"原序即执行序"}</span>
          </div>
        )}
        <div className="格" style={{marginTop:"0.75rem",marginBottom:明细.length? "0.85rem":0}}>
          <div className="卡"><b>{报数.枢纽??0}</b><span>枢纽写入</span></div>
          <div className="卡"><b>{报数.链接??0}</b><span>链接写入</span></div>
          <div className="卡"><b>{报数.卫星??0}</b><span>卫星写入</span></div>
          <div className="卡"><b>{报数.跳过??0}</b><span>跳过</span></div>
        </div>
        {明细.length>0 && (
          <>
            <div className="段题">本批明细</div>
            <ul className="明细">
              {明细.map((d,i)=>(
                <li key={i}><b>{d.类}</b> · {d.业务键} · {d.结果}
                  {d.哈希键 ? <span className="哈希"> · {d.哈希键}</span> : null}
                </li>
              ))}
            </ul>
          </>
        )}
      </div>
    )}

    <div className="段">
      <div className="段题">装载序贯验（只读）</div>
      {!序录.length ? <div className="空态">暂无装载序审计</div> : (
        <table>
          <thead>
            <tr>
              <th>批号</th><th>原序</th><th>执行序</th><th>重排</th>
              <th>结果</th><th>拒绝原因</th><th>半截残留</th>
            </tr>
          </thead>
          <tbody>
            {序录.map(r=>(
              <tr key={r.编号}>
                <td>{r.批次编号}</td>
                <td className="哈希">{(r.原序||[]).join(" → ")||"—"}</td>
                <td className="哈希">{(r.执行序||[]).join(" → ")||"—"}</td>
                <td><span className={`徽章 ${r.是否重排?"败":"淡"}`}>{r.是否重排?"是":"否"}</span></td>
                <td><span className={`徽章 ${r.结果==="成功"?"通":"败"}`}>{r.结果}</span></td>
                <td>{r.拒绝原因||"—"}</td>
                <td><span className={`徽章 ${r.半截残留>0?"败":"淡"}`}>{r.半截残留}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  </div>);
}
