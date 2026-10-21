-- KEYS: seat lock keys (e.g. "hold:{event_id}:{seat_id}")
-- ARGV: [user_id]
local user_id = ARGV[1]

for i, key in ipairs(KEYS) do
    if redis.call('GET', key) == user_id then
        redis.call('DEL', key)
    end
end

return 1
