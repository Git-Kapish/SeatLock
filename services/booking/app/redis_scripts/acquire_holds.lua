-- KEYS: seat lock keys (e.g. "hold:{event_id}:{seat_id}")
-- ARGV: [user_id, ttl_seconds]
local user_id = ARGV[1]
local ttl = tonumber(ARGV[2])

-- 1. Check if ANY key is already held
for i, key in ipairs(KEYS) do
    if redis.call('EXISTS', key) == 1 then
        return {0, key}
    end
end

-- 2. All keys free: acquire all atomically
for i, key in ipairs(KEYS) do
    redis.call('SET', key, user_id, 'EX', ttl)
end

return {1, "OK"}
