# SPDX-License-Identifier: MIT
require 'json'

# Compatibility helper for the pre-existing MU300 f50.iot deployment only.
module F50IotInterval
  DEFAULT = 1200
  def self.seconds(base = '/etc/f50-xiaojing')
    value = JSON.parse(File.read(File.join(base, 'config.json')))['interval_seconds']
    valid?(value) ? value : DEFAULT
  rescue Errno::ENOENT, JSON::ParserError, TypeError
    DEFAULT
  end

  def self.valid?(value)
    value.is_a?(Integer) && (300..86400).cover?(value) && value % 60 == 0
  end

  def self.due_in(base = '/etc/f50-xiaojing', now = Time.now.to_i)
    state = JSON.parse(File.read(File.join(base, 'status.json')))
    attempts = %w[synced_at attempted_at].map do |key|
      value = state[key]
      value if value.is_a?(Integer) && value > 0 && value <= now
    end.compact
    [seconds(base) - (now - (attempts.max || 0)), 0].max
  rescue Errno::ENOENT, JSON::ParserError, TypeError
    0
  end

  def self.configure(slot, value, base: '/etc/f50-xiaojing', lock: '/var/lock/f50-xiaojing.lock')
    return {ok: false, error: 'invalid_interval'} unless [0, 1].include?(slot) && valid?(value)
    File.open(lock, 'a', 0600) do |file|
      return {ok: false, error: 'busy'} unless file.flock(File::LOCK_EX | File::LOCK_NB)
      path = File.join(base, 'config.json')
      cfg = JSON.parse(File.read(path))
      return {ok: false, error: 'other_slot'} unless cfg.fetch('slot', 0).to_s == slot.to_s
      cfg['interval_seconds'] = value
      tmp = "#{path}.#{Process.pid}.new"
      begin
        File.open(tmp, 'w', 0600) { |f| f.write(JSON.generate(cfg) + "\n"); f.flush; f.fsync }
        File.rename(tmp, path)
      ensure
        File.unlink(tmp) if tmp && File.exist?(tmp)
      end
      {ok: true, interval_seconds: value}
    end
  rescue StandardError
    {ok: false, error: 'storage_failed'}
  end
end
