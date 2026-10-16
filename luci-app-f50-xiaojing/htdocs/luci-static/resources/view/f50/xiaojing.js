'use strict';
'require view';
'require rpc';
'require poll';
'require ui';

var getStatus = rpc.declare({object:'f50.xiaojing',method:'status',expect:{'':{}}});
var configure = rpc.declare({object:'f50.xiaojing',method:'configure',params:['payload'],expect:{'':{}}});
var sync = rpc.declare({object:'f50.xiaojing',method:'sync',params:['slot'],expect:{'':{}}});
var errors = {
 disabled:'请先保存配置并启用校正', not_configured:'尚未配置小鲸卡', busy:'已有任务正在运行',
 invalid_config:'设置无效', invalid_slot:'卡槽不匹配', invalid_credentials:'卡号或验证码格式无效',
 operator_unreachable:'小鲸平台连接失败；旧数据已保留', operator_http_error:'小鲸平台返回异常',
 operator_auth_or_data_error:'平台登录失败或数据异常', invalid_operator_values:'平台流量数值异常',
 traffic_unavailable:'当前固件未提供可用的 unisoc.traffic 流量池服务', incompatible_ledger:'流量池接口不兼容',
 calibration_failed:'流量池校正失败', storage_failed:'数据保存失败', service_unavailable:'插件服务不可用',
 sync_failed:'校正失败；旧数据已保留'
};
function failure(code) { return errors[code] || '操作失败，请检查系统日志'; }
function gb(n) { return typeof n === 'number' && Number.isFinite(n) ? n.toFixed(2)+' GB' : '--'; }
function stamp(n) { return n ? new Date(n*1000).toLocaleString() : '尚无记录'; }

return view.extend({
 load:function() { return getStatus(); },
 render:function(data) {
  var self=this;
  this.root=E('div',{},[
   E('h2',{},'小鲸 IoT 流量校正'),
   E('p',{},'从小鲸平台更新当前套餐周期的额度与已用量；每日、自然月历史保持不变。只适用于兼容的 MU300 流量池。'),
   E('div',{'class':'cbi-section'},[
    E('h3',{},'运营商校正状态'),
    E('p',{'id':'xj-state','role':'status','aria-live':'polite'}),
    E('p',{'id':'xj-values'}),E('p',{'id':'xj-times'}),E('p',{'id':'xj-error','role':'status'}),
    E('p',{},'平台数据显示口径为 1024 MB/GB；两次校正之间仍由本机原有计量方式累计。旧数据不代表实时余量。'),
    E('button',{'id':'xj-sync','class':'cbi-button cbi-button-action','click':function(){self.confirmSync();}},'立即同步校正')
   ]),
   E('div',{'class':'cbi-section'},[
    E('h3',{},'同步设置'),
    this.row('启用自动校正',E('input',{'id':'xj-enabled','type':'checkbox'})),
    this.row('SIM 卡槽',E('select',{'id':'xj-slot'},[E('option',{'value':'0'},'SIM 1'),E('option',{'value':'1'},'SIM 2')])),
    this.row('同步间隔（秒，300–86400）',E('input',{'id':'xj-interval','type':'number','min':'300','max':'86400','step':'1'})),
    this.row('小鲸卡号',E('input',{'id':'xj-card','type':'password','autocomplete':'off','maxlength':'64','placeholder':'留空保留原卡号；不会读回已存卡号'})),
    this.row('查询验证码（如需）',E('input',{'id':'xj-verify','type':'password','autocomplete':'new-password','maxlength':'4','placeholder':'更换卡号时留空表示无需验证码'})),
    this.row('允许明文 HTTP 查询',E('input',{'id':'xj-http','type':'checkbox'})),
    E('p',{},'默认仅尝试 HTTPS。勾选 HTTP 代表你接受卡号、验证码和查询内容可能被链路上的第三方读取；不会自动降级或跟随重定向。'),
    E('button',{'id':'xj-save','class':'cbi-button cbi-button-save','click':function(){self.saveConfig();}},'保存设置')
   ])
  ]);
  this.by('enabled').checked=data.enabled===true;this.by('http').checked=data.allow_http===true;
  this.by('slot').value=String(data.slot||0);this.by('interval').value=data.interval||1200;
  this.paint(data);
  this.poller=function(){return self.refresh();};poll.add(this.poller,5);
  return this.root;
 },
 row:function(label,input) { return E('div',{'class':'cbi-value'},[
  E('label',{'class':'cbi-value-title','for':input.id},label),E('div',{'class':'cbi-value-field'},input)]); },
 by:function(key){return this.root.querySelector('#xj-'+key);},
 paint:function(d){
  this.data=d;
  this.by('state').textContent=d.running?'正在同步…':!d.configured?'尚未配置':!d.enabled?'已停用自动校正':
   d.ok&&!d.stale?'最近校正成功':'等待重试 · 旧数据保留';
  this.by('values').textContent='上次平台剩余：'+gb(d.remaining_gb)+' · 周期额度：'+gb(d.quota_gb)+' · 已用：'+gb(d.used_gb);
  this.by('times').textContent='最近成功：'+stamp(d.synced_at)+' · 最近尝试：'+stamp(d.attempted_at);
  this.by('error').textContent=d.error?failure(d.error):d.stale&&d.synced_at?'平台数据已过期，不代表实时余量。':'';
  this.by('sync').disabled=!!this.busy||!!d.running||!d.configured||!d.enabled;
  this.by('save').disabled=!!this.busy||!!d.running;
 },
 refresh:function(){var self=this;if(this.disposed||this.reading)return Promise.resolve();this.reading=true;
  return getStatus().then(function(d){if(!self.disposed)self.paint(d);}).catch(function(){
   if(!self.disposed)self.by('error').textContent='插件状态读取失败，显示值不是实时数据';
  }).finally(function(){self.reading=false;});},
 run:function(action){var self=this;if(this.busy||this.disposed)return Promise.resolve();this.busy=true;this.paint(this.data);
  return Promise.resolve().then(action).catch(function(){ui.addNotification(null,E('p',{},'插件请求失败'),'error');})
   .finally(function(){self.busy=false;if(!self.disposed){self.paint(self.data);self.refresh();}});},
 saveConfig:function(){
  var self=this, interval=Number(this.by('interval').value),slot=Number(this.by('slot').value);
  var payload={enabled:this.by('enabled').checked,allow_http:this.by('http').checked,
   interval:interval,slot:slot,card:this.by('card').value.trim(),verify:this.by('verify').value.trim()};
  if(!Number.isInteger(interval)||interval<300||interval>86400||![0,1].includes(slot)){
   ui.addNotification(null,E('p',{},'间隔或卡槽设置无效'),'error');return;
  }
  return this.run(function(){return configure(JSON.stringify(payload)).then(function(r){
   if(!r.ok){ui.addNotification(null,E('p',{},failure(r.error)),'error');return;}
   self.by('card').value='';self.by('verify').value='';
   ui.addNotification(null,E('p',{},'配置已保存；凭据不会读回页面。'),'info');
  });});
 },
 confirmSync:function(){
  var self=this;if(this.busy||!this.data||this.data.running)return;
  ui.showModal('使用小鲸数据校正？',[
   E('p',{},'将更新 SIM '+(this.data.slot+1)+' 当前周期的额度与已用量；每日和每月历史不变。未保存表单不会提交。'),
   E('div',{'class':'right'},[
    E('button',{'class':'cbi-button','click':ui.hideModal},'取消'),' ',
    E('button',{'class':'cbi-button cbi-button-action','click':function(){ui.hideModal();self.run(function(){return sync(self.data.slot).then(function(r){
     ui.addNotification(null,E('p',{},r.ok?'校正任务已提交，请等待状态刷新':failure(r.error)),r.ok?'info':'error');
    });});}},'开始校正')
   ])
  ]);
 },
 unload:function(){this.disposed=true;if(this.poller)poll.remove(this.poller);},
 handleSaveApply:null,handleSave:null,handleReset:null
});
