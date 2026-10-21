#!/usr/bin/env python3
"""Patch a STAGED copy of the existing MU300 integration, never a live router.

Supply an offline root tree containing the four existing files. Unknown versions
are rejected before any writes. No credentials, network calls or service restarts.
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LIBRARY = 'usr/libexec/f50-xiaojing-interval.rb'
RPC = 'usr/libexec/rpcd/f50.iot'
WORKER = 'usr/libexec/f50-xiaojing-sync.rb'
PAGE = 'www/luci-static/resources/view/mu300/traffic.js'
ACL = 'usr/share/rpcd/acl.d/luci-app-f50-iot.json'


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unsupported or already patched source: ' + old[:80])
    return text.replace(old, new, 1)


def patch_worker(text):
    text = replace_once(text, "require 'json'", "require 'json'\nrequire '/usr/libexec/f50-xiaojing-interval'")
    text = replace_once(text, "    system('/usr/bin/ruby', __FILE__, '--sync')\n    sleep 1200",
        "    # Reload the interval every 5 seconds; saving never queries/calibrates.\n"
        "    sleep 5 while F50IotInterval.due_in > 0\n"
        "    system('/usr/bin/ruby', __FILE__, '--sync')\n    sleep 5")
    return replace_once(text, 'interval_seconds: 1200,', 'interval_seconds: F50IotInterval.seconds,')


def patch_rpc(text):
    text = replace_once(text, "require 'json'", "require 'json'\nrequire '/usr/libexec/f50-xiaojing-interval'")
    text = replace_once(text, 'interval_seconds: 1200,', 'interval_seconds: F50IotInterval.seconds(BASE),')
    text = replace_once(text, '> 1500', "> F50IotInterval.seconds(BASE) + 300")
    text = replace_once(text, '{get: {slot: 0}, sync: {slot: 0}}',
                        '{get: {slot: 0}, sync: {slot: 0}, configure: {slot: 0, interval_seconds: 1200}}')
    text = replace_once(text, '%w[get sync].include?', '%w[get sync configure].include?')
    text = replace_once(text, "    if ARGV[1] == 'get'", """    if ARGV[1] == 'configure'
      # rpcd adds session metadata for authenticated browser calls; never persist it.
      raise ArgumentError unless (input.keys - %w[slot interval_seconds ubus_rpc_session]).empty?
      if !data[:configured]
        puts JSON.generate({ok: false, error: data[:other_slot] ? 'other_slot' : 'not_configured'})
      else
        puts JSON.generate(F50IotInterval.configure(slot, input['interval_seconds']))
      end
    elsif ARGV[1] == 'get'"""
    )
    return text


def patch_page(text):
    text = replace_once(text, 'function iotSlot()', "var callIotConfigure = rpc.declare({ object: 'f50.iot', method: 'configure', params: ['slot','interval_seconds'], expect: {'': {}} });\nfunction iotSlot()")
    text = replace_once(text, "var IOT_ERRORS = {", "var IOT_ERRORS = { invalid_interval:'请输入 5–1440 的整数分钟', storage_failed:'设置保存失败，原设置保留',")
    text = replace_once(text, '每 20 分钟从小鲸平台同步额度与已用量', '按设定间隔从小鲸平台同步额度与已用量')
    text = replace_once(text, ' <div class="mud-tr-actions"><button class="mud-btn on" id="mud-tr-iot-sync" disabled>立即同步校正</button></div>', ''' <div class="mud-tr-actions" style="align-items:center;gap:6px"><button class="mud-btn on" id="mud-tr-iot-sync" disabled>立即同步校正</button><label for="mud-tr-iot-interval" class="mud-tr-sub">每</label><input id="mud-tr-iot-interval" aria-label="自动刷新间隔（分钟）" title="5–1440 整数分钟，默认20；保存只改间隔" type="number" min="5" max="1440" step="1" inputmode="numeric" style="width:60px;min-width:0;box-sizing:border-box;padding:5px 4px;border:1px solid var(--hairline,#ccc);border-radius:6px;background:var(--surface,#fff);color:var(--text,#222)"><span class="mud-tr-sub">分钟</span><button class="mud-btn" id="mud-tr-iot-save" aria-label="保存刷新间隔">保存</button></div>''')
    text = replace_once(text, "'自动校正正常 · 每 20 分钟'", "'自动校正正常 · 每 ' + ((d.interval_seconds || 1200) / 60) + ' 分钟'")
    text = replace_once(text, "'上次平台数据已超过 25 分钟，不代表实时余量。'", "'上次平台数据已超过设定刷新间隔及 5 分钟宽限，不代表实时余量。'")
    text = replace_once(text, "\t\tthis._iotData = d;", """		this._iotData = d;
		if (!this._iotIntervalDirty) this.q('iot-interval').value = (d.interval_seconds || 1200) / 60;
		this.q('iot-save').disabled = !d.configured || !!d.running || !!this._iotSaving || !!this._mutating || !!this._confirming || !!this._iotWaiting;
		this.q('iot-interval').disabled = !d.configured || !!this._iotSaving;
""".rstrip())
    text = replace_once(text, "\t\t\tel.addEventListener('input', function() { self._formDirty = true; });", """			el.addEventListener('input', function() {
				if (el.id === 'mud-tr-iot-interval') self._iotIntervalDirty = true;
				else self._formDirty = true;
			});""".strip('\n'))
    text = replace_once(text, "\t\tthis.q('refresh').onclick", """		this.q('iot-save').onclick = function() {
			if (self._iotSaving || self._mutating || self._confirming || self._iotWaiting || (self._iotData || {}).running) return;
			var minutes = Number(self.q('iot-interval').value), slot = iotSlot();
			if (!Number.isInteger(minutes) || minutes < 5 || minutes > 1440) {
				M.toast('请输入 5–1440 的整数分钟', {type:'error'}); return;
			}
			self._confirming = true; self.paintIot(self._iotData || {});
			M.confirmBox('保存刷新间隔？', '改为每 ' + minutes + ' 分钟查询一次；卡号、额度和流量历史不变，不立即发起校正。', {okText:'保存'}).then(function(yes) {
				if (!yes || self._disposed) return;
				if (iotSlot() !== slot) { M.toast('卡槽已改变，请重新操作', {type:'error'}); return; }
				self._iotSaving = true; self.paintIot(self._iotData || {});
				return callIotConfigure(slot, minutes * 60).then(function(r) {
					if (!r || !r.ok) { M.toast(IOT_ERRORS[r && r.error] || '保存失败', {type:'error'}); return; }
					self._iotIntervalDirty = false;
					M.toast('刷新间隔已保存，自动任务将在 5 秒内读取新设置', {type:'success'});
				});
			}).catch(function() { if (!self._disposed) M.toast('保存请求失败，重新读取确认', {type:'error'}); })
			.finally(function() { self._iotSaving = false; self._confirming = false; if (!self._disposed) self.refreshIot(); });
		};
		this.q('refresh').onclick""".strip('\n'))
    # Serialize all mutation controls while the new interval save is pending.
    text = replace_once(text, 'var busy = d.running || this._iotWaiting;', 'var busy = d.running || this._iotWaiting || this._iotSaving;')
    return text


def plan(root):
    root = Path(root)
    result = {RPC: patch_rpc((root/RPC).read_text()), WORKER: patch_worker((root/WORKER).read_text()),
              PAGE: patch_page((root/PAGE).read_text())}
    acl = json.loads((root/ACL).read_text())
    methods = acl['luci-app-f50-iot']['write']['ubus']['f50.iot']
    if 'configure' not in methods:
        methods.append('configure')
    result[ACL] = json.dumps(acl, ensure_ascii=False, indent=2) + '\n'
    result[LIBRARY] = (REPO/'integrations/mu300/f50-xiaojing-interval.rb').read_text()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('staged_root', type=Path)
    args = parser.parse_args()
    if args.staged_root.resolve() == Path('/'):
        parser.error('Refusing the live root; use an offline staging directory')
    changes = plan(args.staged_root)  # All compatibility checks before writing.
    for relative, content in changes.items():
        (args.staged_root/relative).write_text(content)
        print(relative)
