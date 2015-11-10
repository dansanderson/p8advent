msgs = {
    "it was the best of times",
    "it was the worst of times",
    "some things happened",
    "then some more things happened",
    "but i don't really know what happened",
    "so i probably shouldn't say",
    "some things happened",
    "that's all i know",
    'he stood up. "no," he said. ok.',
    'then i (his brother) laughed.',
    '"uh, maybe?" i shook my head.',
    '"ok (or not)." i sighed.'
}
msg_i = #msgs - 1

function _update()
  if btnp(0) then
    msg_i = (msg_i + 1) % #msgs
  end
end

function _draw()
  cls()
  print(_t(msgs[msg_i+1]), 0, 0, 7)
end
