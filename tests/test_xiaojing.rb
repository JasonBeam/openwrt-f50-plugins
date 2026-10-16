require 'tmpdir'
require 'json'
require_relative '../f50-xiaojing/root/usr/libexec/f50-xiaojing-lib'

class FakeClient < F50::Xiaojing
  attr_accessor :fail_operator, :native_failure, :values
  attr_reader :calls, :original, :saved_payload
  def initialize(**args)
    super
    @calls = []
    @values = {quota_gb: 508.0, used_gb: 300.0, remaining_gb: 208.0}
    @original = {'config'=>{'monthly_gb'=>500,'reset_day'=>26,'count_mode'=>'total',
      'daily_gb'=>0,'device'=>'','plan_name'=>'Example','future_option'=>'preserve'},
      'days'=>[{'date'=>'2026-01-01','rx'=>42,'tx'=>12}], 'months'=>[{'date'=>'2026-01','rx'=>42,'tx'=>12}]}
  end
  def ledger(method, args)
    @calls << [method, args]
    return Marshal.load(Marshal.dump(@original)) if method == 'get'
    @saved_payload = JSON.parse(args.fetch(:payload))
    {'ok' => !@native_failure}
  end
  def operator_values(_cfg)
    raise 'operator_unreachable' if @fail_operator
    @values
  end
end

def check(value, label)
  raise "FAILED: #{label}" unless value
  puts "PASS: #{label}"
end

Dir.mktmpdir('f50-public-review-') do |dir|
  client = FakeClient.new(base: File.join(dir, 'data'), lock: File.join(dir, 'lock'))
  check(!client.status[:enabled] && !client.status[:configured], 'new install disabled without credentials')
  check(client.sync[:error] == 'disabled', 'disabled worker never queries ledger/operator')
  check(client.calls.empty?, 'disabled worker has no ledger effects')
  check(client.configure({'enabled'=>true})[:error] == 'invalid_credentials', 'cannot enable without credentials')
  check(!client.configure({'endpoint'=>'http://attacker.invalid'})[:ok], 'arbitrary endpoint rejected')
  check(!client.configure({'enabled'=>true,'card'=>'fake;command','verify'=>''})[:ok], 'malformed credential rejected')
  check(!client.configure({'interval'=>1})[:ok], 'unsafe sync interval rejected')
  check(client.configure({'enabled'=>true,'card'=>'PUBLIC_TEST_CARD_A','verify'=>'1234'})[:ok], 'valid dummy setup accepted')
  check((File.stat(File.join(dir,'data','config.json')).mode & 0777) == 0600, 'private config permissions')
  check((File.stat(File.join(dir,'data')).mode & 0777) == 0700, 'private config directory')
  old = Marshal.load(Marshal.dump(client.original))
  check(client.sync[:ok], 'operator calibration succeeds in fixture')
  check(client.saved_payload['used_gb'] == 300 && client.saved_payload['monthly_gb'] == 508, 'only expected calibration values replaced')
  check(client.saved_payload['future_option'] == 'preserve' && client.saved_payload['reset_day'] == 26, 'unknown options and reset day preserved')
  check(client.original == old, 'no changes to fixture daily/monthly records')
  safe = JSON.generate(client.status)
  check(!safe.include?('PUBLIC_TEST_CARD') && !safe.include?('1234'), 'status never exposes credentials')
  client.fail_operator = true
  count = client.calls.count{|method,_|method=='set'}
  check(client.sync[:error] == 'operator_unreachable', 'operator failure classified')
  check(client.calls.count{|method,_|method=='set'} == count, 'operator failure never calibrates')
  status = client.status
  check(status[:ok] == false && status['remaining_gb'] == 208 && status['synced_at'], 'failed query keeps prior successful snapshot')
  File.open(File.join(dir,'lock'),'a') do |lock|
    lock.flock(File::LOCK_EX)
    check(client.sync[:error] == 'busy' && client.status[:running], 'concurrent work blocked by kernel lock')
    check(client.configure({'enabled'=>false})[:error] == 'busy', 'cannot change account during sync')
  end
  client.fail_operator = false
  before = File.read(File.join(dir,'data','status.json'))
  check(client.sync(preview:true)[:preview], 'preview returns safe quota values')
  check(File.read(File.join(dir,'data','status.json')) == before, 'preview does not rewrite status')
  check(client.calls.count{|method,_|method=='set'} == count, 'preview does not change ledger')
  client.native_failure = true
  check(client.sync[:error] == 'calibration_failed', 'native ledger failure is not a successful sync')
  check(client.configure({'card'=>'PUBLIC_TEST_CARD_B','slot'=>1})[:ok], 'account switch accepted')
  check(!client.status.key?('remaining_gb'), 'previous SIM snapshot invalidated')
  check(client.config['verify'] == '', 'account switch never reuses previous verification code')
end
