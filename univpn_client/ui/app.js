'use strict';
const $ = id => document.getElementById(id);
const titles = {connection:'连接',profiles:'网关配置',accounts:'账户',logs:'连接日志',settings:'设置'};
let snapshot = null, editing = null, currentPage = 'connection', refreshing = false;
let selectedProfile = null, selectedAccount = null, toastTimer, renderedConfig = null;
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
function toast(text) { $('toast').textContent = text; $('toast').classList.remove('hidden'); clearTimeout(toastTimer); toastTimer = setTimeout(()=>$('toast').classList.add('hidden'),5000); }
async function api(method, params={}) {
  const result = await window.pywebview.api.call(method,params);
  if (result.error) throw new Error(result.error);
  return result.result;
}
function theme(value) { document.documentElement.dataset.theme = value==='system' ? (darkQuery.matches?'dark':'light') : value; }
darkQuery.addEventListener('change',()=>theme(snapshot?.config.theme||'system'));
function page(name) { currentPage = name; Object.keys(titles).forEach(id=>$(id).classList.toggle('hidden',id!==name)); document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===name)); $('page-title').textContent=titles[name]; if (name==='logs') refreshLogs(); }
function button(text, label, action, className='icon-button') { const b=document.createElement('button'); b.textContent=text; b.title=label; b.setAttribute('aria-label',label); b.className=className; b.onclick=()=>Promise.resolve(action()).catch(e=>toast(e.message)); return b; }
function empty(list,text) { const el=document.createElement('div'); el.className='empty'; el.textContent=text; list.append(el); }
function row(item, detail, edit, remove, selectable=false) {
  const r=document.createElement('div'); r.className='row'+(selectable&&item.id===selectedProfile?' selected':'');
  if(selectable) r.append(button('','选择 '+item.name, async()=>{ if(snapshot.connection.state!=='disconnected'&&snapshot.connection.state!=='failed') {toast('请先断开当前 VPN，再切换网关');return;} selectedProfile=item.id; await api('select',{profile_id:selectedProfile,account_id:selectedAccount}); await refresh(); },'radio'));
  const body=document.createElement('div'); body.className='row-body'; const n=document.createElement('div'); n.className='row-name'; n.textContent=item.name; const d=document.createElement('div'); d.className='row-detail'; d.textContent=detail; body.append(n,d);r.append(body);
  r.append(button('✎','编辑 '+item.name,edit)); if(remove)r.append(button('⌫','删除 '+item.name,remove,'icon-button danger'));return r;
}
function render(data) {
  snapshot=data; const config=data.config, connection=data.connection;
  selectedProfile=config.selected_profile;selectedAccount=config.selected_account;
  $('version').textContent='v'+data.version; theme(config.theme);$('theme-select').value=config.theme;
  const labels={disconnected:'未连接',connecting:'连接中',connected:'已连接',reconnecting:'重新连接中',disconnecting:'正在断开',failed:'连接失败'};
  $('status-text').textContent=labels[connection.state]||connection.state;
  $('status-dot').className=connection.state==='connected'?'connected':['connecting','reconnecting','disconnecting'].includes(connection.state)?'busy':'';
  const active=!['disconnected','failed'].includes(connection.state);$('toggle').setAttribute('aria-checked',String(active));$('toggle').disabled=connection.state==='disconnecting';
  $('connection-title').textContent=labels[connection.state]||connection.state;
  const gateway=config.profiles.find(x=>x.id===connection.profile_id);
  $('connection-description').textContent=connection.error || (active&&gateway ? gateway.name+' · '+gateway.host : '选择网关与账户，然后连接。');
  $('account-select').disabled=active;
  const configKey=JSON.stringify(config); if(configKey===renderedConfig)return;renderedConfig=configKey;
  $('account-select').replaceChildren(); const prompt=document.createElement('option');prompt.value='';prompt.textContent='请选择账户';$('account-select').append(prompt);
  config.accounts.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' — '+a.username;$('account-select').append(o);});$('account-select').value=selectedAccount||'';$('account-select').disabled=active;
  ['connection-profiles','profile-list','account-list'].forEach(id=>$(id).replaceChildren());
  for(const p of config.profiles){const detail=p.host+':'+p.port+' · '+(p.routes.length?p.routes.length+' 条分流路由':'未配置路由');$('connection-profiles').append(row(p,detail,()=>editor('profile',p),null,true));$('profile-list').append(row(p,detail,()=>editor('profile',p),()=>remove('profiles',p)));}
  for(const a of config.accounts)$('account-list').append(row(a,a.username+' · 系统凭据库',()=>editor('account',a),()=>remove('accounts',a)));
  if(!config.profiles.length){empty($('connection-profiles'),'添加你的第一个 VPN 网关');empty($('profile-list'),'网关配置会在本机保存，方便切换。');}
  if(!config.accounts.length)empty($('account-list'),'新建账户并保存密码，连接时无需重复填写。');
}
async function refresh(){if(refreshing)return;refreshing=true;try{render(await api('snapshot'));}catch(e){$('status-text').textContent='本地服务不可用';toast(e.message);}finally{refreshing=false;}}
async function refreshLogs(){try{const logs=await api('logs');$('log-output').textContent=logs.length?logs.map(x=>new Date(x.time*1000).toLocaleTimeString()+'  '+x.message).join('\n'):'暂无日志';}catch(e){toast(e.message);}}
async function remove(kind,item){if(!confirm('删除“'+item.name+'”？'+(kind==='accounts'?'已保存的密码也会删除。':'')))return;await api('delete',{kind,item_id:item.id});await refresh();}
function field(name,label,value='',type='text') { const wrap=document.createElement('div');wrap.className='field';const l=document.createElement('label');l.textContent=label;l.htmlFor='field-'+name;const i=document.createElement(type==='textarea'?'textarea':'input');i.id=l.htmlFor;i.name=name;if(type!=='textarea')i.type=type;i.value=value;wrap.append(l,i);$('fields').append(wrap);return i; }
function editor(kind,item={}) { editing={kind,item};$('fields').replaceChildren();$('form-error').textContent='';$('editor-title').textContent=(item.id?'编辑':'新建')+(kind==='profile'?'网关':'账户');field('name','备注名称',item.name||'').required=true;
 if(kind==='profile'){field('host','网关地址（不含 https://）',item.host||'').required=true;const p=field('port','端口',item.port||443,'number');p.min=1;p.max=65535;p.required=true;field('domain','认证域（留空则使用网关地址）',item.domain||'');field('routes','IPv4 分流路由（每行一条，例如 10.0.0.0/8）',(item.routes||[]).join('\n'),'textarea');field('cafile','CA 证书文件路径（可选）',item.cafile||'');field('pin','OpenConnect pin-sha256 指纹（可选）',item.pin||'');}
 else{field('username','用户名',item.username||'').required=true;const p=field('password',item.id?'新密码（留空保留原密码）':'密码','','password');p.autocomplete='new-password';p.required=!item.id;}
 $('editor').showModal();$('fields').querySelector('input').focus(); }
$('editor-form').onsubmit=async e=>{e.preventDefault();const f=Object.fromEntries(new FormData(e.target));let value={name:f.name};if(editing.item.id)value.id=editing.item.id;const save=e.submitter;save.disabled=true;try{if(editing.kind==='profile'){Object.assign(value,{host:f.host,port:Number(f.port),domain:f.domain,routes:f.routes.split(/\n/).map(x=>x.trim()).filter(Boolean),cafile:f.cafile,pin:f.pin});await api('save_profile',{value});}else{value.username=f.username;await api('save_account',{value,...(f.password?{password:f.password}:{})});}e.target.reset();$('editor').close();await refresh();}catch(error){$('form-error').textContent=error.message;}finally{save.disabled=false;}};
['close-editor','cancel-editor'].forEach(id=>$(id).onclick=()=>{$('editor-form').reset();$('editor').close();});
$('editor').addEventListener('close',()=>{$('editor-form').reset();editing=null;});
$('toggle').onclick=async()=>{try{if(!snapshot)return;const active=!['disconnected','failed'].includes(snapshot.connection.state);if(active)await api('disconnect');else{if(!selectedProfile||!selectedAccount){toast('请先选择网关与账户');return;}await api('connect',{profile_id:selectedProfile,account_id:selectedAccount});}await refresh();}catch(e){toast(e.message);}};
$('account-select').onchange=async e=>{selectedAccount=e.target.value||null;try{await api('select',{profile_id:selectedProfile,account_id:selectedAccount});await refresh();}catch(error){toast(error.message);}};
$('theme-select').onchange=async e=>{try{await api('set_theme',{theme:e.target.value});await refresh();}catch(error){toast(error.message);}};
['add-profile','quick-profile'].forEach(id=>$(id).onclick=()=>editor('profile'));['add-account','quick-account'].forEach(id=>$(id).onclick=()=>editor('account'));
document.querySelectorAll('.nav').forEach(x=>x.onclick=()=>page(x.dataset.page));$('refresh-logs').onclick=refreshLogs;
['export-config','import-config'].forEach(id=>$(id).onclick=async()=>{try{const result=await window.pywebview.api[id==='export-config'?'export_file':'import_file']();if(result.error)throw Error(result.error);if(result.result){toast(id==='export-config'?'配置已导出（不含密码）':'配置已导入');await refresh();}}catch(e){toast(e.message);}});
$('shutdown').onclick=async()=>{if(!confirm('退出服务并断开 VPN？'))return;try{await api('shutdown');window.pywebview.api.close_window();}catch(e){toast(e.message);}};
window.addEventListener('pywebviewready',()=>{refresh();setInterval(()=>{refresh();if(currentPage==='logs')refreshLogs();},1500);});
