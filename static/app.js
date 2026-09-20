let chart;

function esc(value){
  return String(value ?? "—").replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
}

function renderDevices(data){
  const rows = data.devices.map(d => `
    <tr>
      <td><span class="status ${d.status.toLowerCase()}"><i></i>${d.status}</span></td>
      <td class="mono">${esc(d.ip)}</td>
      <td>${esc(d.type)}</td>
      <td class="mono">${esc(d.mac)}</td>
      <td>${d.latency == null ? "—" : esc(d.latency) + " ms"}</td>
      <td>${esc(d.last_seen)}</td>
    </tr>`).join("");
  document.getElementById("deviceRows").innerHTML = rows || '<tr><td colspan="6" class="empty">No devices discovered yet.</td></tr>';
  document.getElementById("deviceCount").textContent = `${data.total} DEVICES`;
}

function renderIntel(data){
  const rows=data.devices.map(d=>`
    <tr>
      <td class="mono">${esc(d.ip)}</td>
      <td>${esc(d.os || "Unknown")}</td>
      <td>${d.ttl == null ? "—" : esc(d.ttl)}</td>
      <td>${esc(d.type)}</td>
      <td><span class="status ${d.status.toLowerCase()}"><i></i>${esc(d.status)}</span></td>
    </tr>`).join("");
  document.getElementById("intelRows").innerHTML=rows || '<tr><td colspan="5" class="empty">No devices discovered.</td></tr>';
}

function renderAlerts(data){
  const el = document.getElementById("alertsList");
  if(!data.alerts.length){el.innerHTML='<div class="empty">No alerts yet.</div>';return;}
  el.innerHTML=data.alerts.slice(0,12).map(a=>`
    <div class="alert-item ${esc(a.level)}">
      <div class="alert-time">${esc(a.time)}</div>
      <div class="alert-msg">${esc(a.message)}</div>
    </div>`).join("");
}

function renderLogs(data){
  const el=document.getElementById("logsList");
  if(!data.logs.length){el.innerHTML='<div class="empty">No log entries.</div>';return;}
  el.innerHTML=data.logs.slice(0,35).map(l=>`
    <div class="log ${l.level==='ALERT'?'alert':''} ${l.level==='ERROR'?'error':''}">
      <span class="time">${esc(l.time)}</span><span class="level">${esc(l.level)}</span><span>${esc(l.message)}</span>
    </div>`).join("");
}

function updateChart(history){
  const labels=history.map(x=>x.time), values=history.map(x=>x.latency);
  if(!chart){
    chart=new Chart(document.getElementById("latencyChart"),{
      type:"line",
      data:{labels,datasets:[{label:"Latency",data:values,borderColor:"#35e58b",backgroundColor:"rgba(53,229,139,.08)",fill:true,tension:.35,pointRadius:1.5,borderWidth:2}]},
      options:{responsive:true,maintainAspectRatio:false,animation:false,
        scales:{x:{grid:{color:"#15212d"},ticks:{color:"#5d7186",font:{size:9},maxTicksLimit:10}},
                y:{beginAtZero:true,grid:{color:"#15212d"},ticks:{color:"#5d7186",font:{size:9},callback:v=>v+" ms"}}},
        plugins:{legend:{display:false},tooltip:{backgroundColor:"#0a1119",borderColor:"#25394c",borderWidth:1}}
      }
    });
  }else{chart.data.labels=labels;chart.data.datasets[0].data=values;chart.update("none");}
}

async function refresh(){
  try{
    const res=await fetch("/api/status",{cache:"no-store"}); const data=await res.json();
    document.getElementById("online").textContent=data.online;
    document.getElementById("offline").textContent=data.offline;
    document.getElementById("latency").innerHTML=`${data.latency}<small> ms</small>`;
    document.getElementById("packets").textContent=data.packets.toLocaleString();
    document.getElementById("updated").textContent=`Last update ${new Date().toLocaleTimeString()}`;
    renderDevices(data);renderIntel(data);renderAlerts(data);renderLogs(data);updateChart(data.history);
  }catch(e){document.getElementById("updated").textContent="Backend disconnected";}
}
document.getElementById("discoverBtn").onclick=async()=>{await fetch("/api/discover",{method:"POST"});refresh();};
document.getElementById("clearBtn").onclick=async()=>{await fetch("/api/clear-logs",{method:"POST"});refresh();};
refresh();setInterval(refresh,2000);


async function sendNotification(){
  const input=document.getElementById("notifyMessage");
  const message=input.value.trim();
  if(!message)return;
  const res=await fetch("/api/notify",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message})});
  if(res.ok){
    if("Notification" in window){
      if(Notification.permission==="granted") new Notification("Network Monitor", {body:message});
      else if(Notification.permission!=="denied") {
        const permission=await Notification.requestPermission();
        if(permission==="granted") new Notification("Network Monitor",{body:message});
      }
    }
    input.value="";
    refresh();
  }
}
document.getElementById("notifyBtn").onclick=sendNotification;
document.getElementById("notifyMessage").addEventListener("keydown",e=>{if(e.key==="Enter")sendNotification();});
