msgs = {
    "it was the best of times",
    "it was the worst of times",
    "some things happened",
    "then some more things happened",
    "but i don't really know what happened",
    "so i probably shouldn't say",
    "some things happened",
    "that's all i know"
}
msg_i = #msgs - 1
timer = 0

function _update()
  if timer == 0 then
    msg_i = (msg_i + 1) % #msgs
    timer = 30
  end
  timer = timer - 1
end

function _draw()
  cls()
  print(t(msgs[msg_i+1]), 0, 0, 7)
end
