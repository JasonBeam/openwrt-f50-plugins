# SPDX-License-Identifier: MIT
require 'json'

module F50
  class Xiaojing
    DEFAULTS = {'enabled' => false, 'slot' => 0, 'interval' => 1200, 'allow_http' => false}.freeze
    ERRORS = %w[disabled not_configured busy invalid_config invalid_slot invalid_credentials
      operator_unreachable operator_http_error operator_auth_or_data_error
      invalid_operator_values traffic_unavailable incompatible_ledger calibration_failed
      storage_failed sync_failed].freeze

    def initialize(base: '/etc/f50-xiaojing', lock: '/var/lock/f50-xiaojing.lock')
      @base, @lock = base, lock
    end

    def read_json(name)
      value = JSON.parse(File.read(File.join(@base, name)))
      value.is_a?(Hash) ? value : {}
    rescue Errno::ENOENT, JSON::ParserError
      {}
    end

    def config
      DEFAULTS.merge(read_json('config.json'))
    end

    def configured?(cfg)
      cfg['card'].is_a?(String) && cfg['card'].match?(/\A[a-zA-Z0-9_-]{1,64}\z/) &&
        cfg.fetch('verify', '').is_a?(String) && cfg.fetch('verify', '').match?(/\A[0-9]{0,4}\z/)
    end

    def valid_config?(cfg)
      [true, false].include?(cfg['enabled']) && [true, false].include?(cfg['allow_http']) &&
        [0, 1].include?(cfg['slot']) && cfg['interval'].is_a?(Integer) &&
        (300..86400).cover?(cfg['interval'])
    end

    def atomic(name, data)
      Dir.mkdir(@base, 0700) unless Dir.exist?(@base)
      File.chmod(0700, @base)
      path = File.join(@base, name)
      temp = "#{path}.#{Process.pid}.new"
      File.open(temp, 'w', 0600) { |f| f.write(JSON.generate(data) + "\n"); f.flush; f.fsync }
      File.rename(temp, path)
      true
    ensure
      File.unlink(temp) if temp && File.exist?(temp)
    end

    def locked?
      File.open(@lock, 'a', 0600) { |f| !f.flock(File::LOCK_EX | File::LOCK_NB) }
    end

    def with_lock
      File.open(@lock, 'a', 0600) do |f|
        return {ok: false, error: 'busy'} unless f.flock(File::LOCK_EX | File::LOCK_NB)
        yield
      end
    end

    def status
      cfg = config
      saved = read_json('status.json')
      # Never expose a prior SIM/account's values after changing configuration.
      saved = {} unless saved['slot'] == cfg['slot']
      data = {configured: configured?(cfg), enabled: cfg['enabled'] == true,
        allow_http: cfg['allow_http'] == true, slot: cfg['slot'], interval: cfg['interval'],
        running: locked?, ok: saved['ok'] == true, now: Time.now.to_i}
      %w[synced_at attempted_at quota_gb used_gb remaining_gb].each do |key|
        value = saved[key]
        data[key] = value if value.is_a?(Numeric) && value.finite? && value >= 0
      end
      data[:error] = ERRORS.include?(saved['error']) ? saved['error'] : nil
      data[:stale] = !data['synced_at'] || Time.now.to_i - data['synced_at'] > cfg['interval'].to_i + 300
      data
    end

    def configure(input)
      return {ok: false, error: 'invalid_config'} unless input.is_a?(Hash) &&
        (input.keys - %w[enabled slot interval allow_http card verify]).empty?
      with_lock do
        old = config
        updated = old.merge(input.reject { |key, value| %w[card verify].include?(key) && value == '' })
        if input['card'].is_a?(String) && !input['card'].empty? && input['card'] != old['card']
          updated['verify'] = input.fetch('verify', '')
        end
        return {ok: false, error: 'invalid_config'} unless valid_config?(updated)
        return {ok: false, error: 'invalid_credentials'} if updated['enabled'] && !configured?(updated)
        # Changing SIM/account invalidates only the operator snapshot, never the ledger.
        changed = %w[slot card verify].any? { |key| updated[key] != old[key] }
        if changed
          atomic('status.json', {ok: false, slot: updated['slot'], error: 'not_configured'})
        end
        atomic('config.json', updated)
        {ok: true}
      end
    rescue StandardError
      {ok: false, error: 'storage_failed'}
    end

    def ledger(method, arguments)
      text = IO.popen(['ubus', '-t', '5', 'call', 'unisoc.traffic', method,
        JSON.generate(arguments)], err: File::NULL, &:read)
      raise 'traffic_unavailable' unless $?.success?
      JSON.parse(text)
    rescue JSON::ParserError
      raise 'traffic_unavailable'
    end

    def http_json(url, cookie_dir, body = nil)
      settings = ["url = #{url.to_json}", 'silent', 'show-error', 'max-time = 20',
        'connect-timeout = 8', 'max-filesize = 65536', 'max-redirs = 0',
        "cookie-jar = #{File.join(cookie_dir, 'cookies').to_json}",
        "cookie = #{File.join(cookie_dir, 'cookies').to_json}",
        'write-out = "\\n%{http_code}"']
      if body
        settings << 'header = "Content-Type: application/x-www-form-urlencoded; charset=UTF-8"'
        settings << "data = #{body.to_json}"
      end
      # Explicit protocol and no redirects: no silent downgrade or credential forwarding.
      protocol = url.start_with?('https:') ? '=https' : '=http'
      raw = IO.popen(['curl', '--proto', protocol, '--config', '-'], 'r+', err: File::NULL) do |io|
        io.write(settings.join("\n") + "\n"); io.close_write; io.read
      end
      raise 'operator_unreachable' unless $?.success?
      payload, _, code = raw.rpartition("\n")
      raise 'operator_http_error' unless code == '200'
      result = JSON.parse(payload)
      raise 'operator_auth_or_data_error' unless result.is_a?(Hash) && result['data'].is_a?(Hash)
      result['data']
    rescue JSON::ParserError
      raise 'operator_auth_or_data_error'
    end

    def operator_values(cfg)
      # Private temporary cookie directory. No credentials in argv, logs or UI replies.
      directory = "/tmp/f50-xiaojing-#{Process.pid}"
      Dir.mkdir(directory, 0700)
      scheme = cfg['allow_http'] ? 'http' : 'https'
      base = "#{scheme}://1.mywuliankj.cn"
      http_json("#{base}/app/card/login", directory, "card=#{cfg['card']}&verify=#{cfg.fetch('verify', '')}")
      data = http_json("#{base}/app/client/card/get", directory)
      used = Float(data.fetch('used', data['realUsed']))
      free = Float(data.fetch('free'))
      raise 'invalid_operator_values' unless [used, free].all? { |v| v.finite? && v >= 0 && v < 102_400_000 }
      raise 'invalid_operator_values' unless used + free > 0 && used + free <= 102_400_000
      # Match the portal display (1024 MB per displayed GB), not an assertion
      # that the native ledger uses binary byte units between calibrations.
      {quota_gb: (used + free) / 1024.0, used_gb: used / 1024.0, remaining_gb: free / 1024.0}
    rescue ArgumentError, TypeError, KeyError
      raise 'invalid_operator_values'
    ensure
      if directory && Dir.exist?(directory)
        cookie = File.join(directory, 'cookies')
        File.unlink(cookie) if File.exist?(cookie)
        Dir.rmdir(directory)
      end
    end

    def sync(preview: false)
      with_lock do
        cfg = config
        previous = read_json('status.json')
        begin
          raise 'invalid_config' unless valid_config?(cfg)
          raise 'disabled' unless preview || cfg['enabled']
          raise 'not_configured' unless configured?(cfg)
          # Check compatibility BEFORE querying the operator or changing anything.
          current = ledger('get', {slot: cfg['slot']})
          raise 'incompatible_ledger' unless current.is_a?(Hash) && current['config'].is_a?(Hash) &&
            %w[monthly_gb reset_day count_mode].all? { |key| current['config'].key?(key) }
          values = operator_values(cfg)
          return {ok: true, preview: true}.merge(values) if preview
          # Re-read to preserve settings edited while the HTTP request was in flight.
          fresh = ledger('get', {slot: cfg['slot']})
          raise 'incompatible_ledger' unless fresh['config'].is_a?(Hash)
          update = fresh['config'].dup
          update['monthly_gb'] = values[:quota_gb].round(6)
          update['used_gb'] = values[:used_gb].round(6)
          result = ledger('set', {slot: cfg['slot'], payload: JSON.generate(update)})
          raise 'calibration_failed' unless result['ok'] == true || result['ok'] == 1
          atomic('status.json', values.merge(ok: true, slot: cfg['slot'],
            synced_at: Time.now.to_i, attempted_at: Time.now.to_i, error: nil))
          {ok: true}
        rescue StandardError => error
          label = ERRORS.include?(error.message) ? error.message : 'sync_failed'
          unless preview
            previous = {} unless previous['slot'] == cfg['slot']
            atomic('status.json', previous.merge('ok' => false, 'error' => label,
              'slot' => cfg['slot'], 'attempted_at' => Time.now.to_i))
          end
          {ok: false, error: label}
        end
      end
    rescue StandardError
      {ok: false, error: 'storage_failed'}
    end
  end
end
