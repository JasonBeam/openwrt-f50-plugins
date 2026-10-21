require 'tmpdir'
require 'json'
require_relative '../integrations/mu300/f50-xiaojing-interval'

def check(value, label)
  raise "FAILED: #{label}" unless value
  puts "PASS: #{label}"
end

Dir.mktmpdir('iot-interval-') do |dir|
  cfg = {'slot'=>0, 'card'=>'PUBLIC_TEST_CARD', 'verify'=>'1234', 'unknown'=>'preserve'}
  path = File.join(dir, 'config.json')
  status = File.join(dir, 'status.json')
  File.write(path, JSON.generate(cfg))
  File.write(status, JSON.generate({'synced_at'=>1000, 'attempted_at'=>1100, 'remaining_gb'=>10}))
  original_status = File.read(status)
  lock = File.join(dir, 'lock')
  check(F50IotInterval.seconds(dir) == 1200, 'legacy config defaults to 20 minutes')
  [nil, '', '300', 0, 299, 301, 300.0, 86460, true].each do |value|
    before = File.read(path)
    check(!F50IotInterval.configure(0, value, base: dir, lock: lock)[:ok], "invalid interval rejected #{value.inspect}")
    check(File.read(path) == before, 'rejection preserves config bytes')
  end
  [300, 1800, 86400].each do |value|
    check(F50IotInterval.configure(0, value, base: dir, lock: lock)[:ok], 'valid minute interval accepted')
    check(JSON.parse(File.read(path)) == cfg.merge('interval_seconds'=>value), 'credentials and unknown fields preserved')
    check(File.read(status) == original_status, 'save does not calibrate or rewrite snapshot')
    check((File.stat(path).mode & 0777) == 0600, 'config stays private')
  end
  check(F50IotInterval.due_in(dir, 1200) == 86300, 'schedule follows last attempted query')
  F50IotInterval.configure(0, 300, base: dir, lock: lock)
  check(F50IotInterval.due_in(dir, 1200) == 200, 'shortening interval updates schedule')
  check(F50IotInterval.due_in(dir, 1500) == 0, 'overdue schedule is due')
  check(F50IotInterval.configure(1, 600, base: dir, lock: lock)[:error] == 'other_slot', 'other SIM rejected')
  File.open(lock, 'a') do |f|
    f.flock(File::LOCK_EX)
    check(F50IotInterval.configure(0, 600, base: dir, lock: lock)[:error] == 'busy', 'save serializes with sync')
  end
  File.write(path, '{broken')
  check(F50IotInterval.seconds(dir) == 1200, 'invalid legacy config has bounded fallback')
end
