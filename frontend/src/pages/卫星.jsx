import React,{useEffect,useState} from "react";
import {取} from "../api.js";

export default function 卫星(){
  const [类,设类]=useState("套餐");
  const [行,设行]=useState([]);
  const 刷=()=>取("/卫星/"+encodeURIComponent(类)+"?仅当前=0").then(设行);
  useEffect(()=>{刷();},[类]);
  return (<div>
    <h1 className="题">卫星</h1>
    <p className="述">属性按载荷哈希开版；同哈希不空开；旧版「是否当前」置否。</p>
    <div className="行">
      {["号卡","套餐","客户","订购"].map(x=>
        <button key={x} className={类===x?"":"次"} onClick={()=>设类(x)}>{x}</button>)}
      <button className="次" onClick={刷}>刷新</button>
      <span className="徽章 淡">{行.length} 条</span>
    </div>
    {!行.length ? <div className="空态">该类卫星尚无记录。</div> : (
      <table>
        <thead><tr><th>编号</th><th>父哈希</th><th>装载日</th><th>载荷哈希</th><th>当前</th><th>属性</th></tr></thead>
        <tbody>{行.map(r=>{
          const 父=r.号卡哈希||r.套餐哈希||r.客户哈希||r.链接哈希;
          return (
            <tr key={r.编号}>
              <td>{r.编号}</td>
              <td className="哈希">{父}</td>
              <td>{r.装载日}</td>
              <td className="哈希">{r.载荷哈希}</td>
              <td><span className={`徽章 ${r.是否当前?"通":"淡"}`}>{r.是否当前?"当前":"历史"}</span></td>
              <td>{r.属性}</td>
            </tr>
          );
        })}</tbody>
      </table>
    )}
  </div>);
}
