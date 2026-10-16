'use strict';
'require view';
'require form';
'require rpc';
'require ui';
'require poll';

var getStatus=rpc.declare({object:'f50.ra',method:'status',expect:{'':{}}});
var request=rpc.declare({object:'f50.ra',method:'request',expect:{'':{}}});

return view.extend({
 load:function(){return getStatus();},
 render:function(data){
  var self=this,m=new form.Map('f50_ra','IPv6 RA 刷新',
   '仅在指定 WAN 的 RA 默认路由剩余寿命偏低或缺失时请求真实 RA。不会删路由、修改 DNS、重启网络或切换系统。');
  var section=m.section(form.NamedSection,'main','main','设置');section.addremove=false;
  var o=section.option(form.Flag,'enabled','启用');o.default='0';o.rmempty=false;
  o=section.option(form.Value,'network','逻辑 WAN 接口');o.default='wan';o.datatype='uciname';o.rmempty=false;
  o=section.option(form.Value,'device_prefix','允许的网卡前缀');o.default='sipa_eth';o.rmempty=false;
  o=section.option(form.Value,'interval','检查间隔（秒）');o.datatype='range(60,86400)';o.default='3600';o.rmempty=false;
  o=section.option(form.Value,'threshold','RA 寿命阈值（秒）');o.datatype='range(60,604800)';o.default='7200';o.rmempty=false;
  this.statusNode=E('p',{'role':'status','aria-live':'polite'});
  this.paint(data);
  return m.render().then(function(map){
   self.button=E('button',{'class':'cbi-button cbi-button-action','click':function(){
    if(self.busy)return;self.busy=true;self.button.disabled=true;
    request().then(function(r){ui.addNotification(null,E('p',{},r.ok?'检查任务已提交；健康的 RA 不会额外发送请求':'任务提交失败'),'info');})
     .catch(function(){ui.addNotification(null,E('p',{},'请求失败'),'error');})
     .finally(function(){self.busy=false;self.refresh();});
   }},'按阈值检查一次');
   self.paint(data);
   self.poller=function(){return self.refresh();};poll.add(self.poller,10);
   return E('div',{},[map,E('div',{'class':'cbi-section'},[
    E('h3',{},'当前状态'),self.statusNode,
    E('p',{},'必须有可信来源、匹配设备架构的 rdisc6。缺少工具或 WAN 不匹配时只提示，不更改网络。'),self.button
   ])]);
  });
 },
 paint:function(d){
  var text=!d.ok?'配置或状态读取失败':!d.tool_available?'缺少 rdisc6：不会执行刷新':!d.enabled?'自动刷新已关闭':
   !d.wan_ready?'指定 WAN 尚未就绪':d.device+' · RA 剩余 '+(d.remaining==null?'未知':d.remaining+' 秒')+
    ' · 检查间隔 '+d.interval+' 秒 · 阈值 '+d.threshold+' 秒';
  this.statusNode.textContent=text;
  if(this.button)this.button.disabled=!!this.busy||!d.ok||!d.enabled||!d.tool_available||!d.wan_ready;
 },
 refresh:function(){var self=this;if(this.disposed||this.reading)return Promise.resolve();this.reading=true;
  return getStatus().then(function(d){if(!self.disposed)self.paint(d);})
   .catch(function(){if(!self.disposed)self.paint({});}).finally(function(){self.reading=false;});},
 unload:function(){this.disposed=true;if(this.poller)poll.remove(this.poller);}
});
