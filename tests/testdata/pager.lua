printer = nil
msgs = {

*"one"..*"two",

*"Book the First--Recalled to Life",

*"I. The Period",

*"It was the best of times, it was the worst of times,
it was the age of wisdom, it was the age of foolishness,
it was the epoch of belief, it was the epoch of incredulity,
it was the season of Light, it was the season of Darkness,
it was the spring of hope, it was the winter of despair,
we had everything before us, we had nothing before us,
we were all going direct to Heaven,
we were all going direct the other way--
in short, the period was so far like the present period, that some of
its noisiest authorities insisted on its being received, for good or for
evil, in the superlative degree of comparison only.",

*"There were a king with a large jaw and a queen with a plain face, on the
throne of England; there were a king with a large jaw and a queen with
a fair face, on the throne of France. In both countries it was clearer
than crystal to the lords of the State preserves of loaves and fishes,
that things in general were settled for ever.",

*"Yeah baby!",

*"It was the year of Our Lord one thousand seven hundred and seventy-five.
Spiritual revelations were conceded to England at that favoured period,
as at this. Mrs. Southcott had recently attained her five-and-twentieth
blessed birthday, of whom a prophetic private in the Life Guards had
heralded the sublime appearance by announcing that arrangements were
made for the swallowing up of London and Westminster. Even the Cock-lane
ghost had been laid only a round dozen of years, after rapping out its
messages, as the spirits of this very year last past (supernaturally
deficient in originality) rapped out theirs. Mere messages in the
earthly order of events had lately come to the English Crown and People,
from a congress of British subjects in America: which, strange
to relate, have proved more important to the human race than any
communications yet received through any of the chickens of the Cock-lane
brood.",

*"France, less favoured on the whole as to matters spiritual than her
sister of the shield and trident, rolled with exceeding smoothness down
hill, making paper money and spending it. Under the guidance of her
Christian pastors, she entertained herself, besides, with such humane
achievements as sentencing a youth to have his hands cut off, his tongue
torn out with pincers, and his body burned alive, because he had not
kneeled down in the rain to do honour to a dirty procession of monks
which passed within his view, at a distance of some fifty or sixty
yards. It is likely enough that, rooted in the woods of France and
Norway, there were growing trees, when that sufferer was put to death,
already marked by the Woodman, Fate, to come down and be sawn into
boards, to make a certain movable framework with a sack and a knife in
it, terrible in history. It is likely enough that in the rough outhouses
of some tillers of the heavy lands adjacent to Paris, there were
sheltered from the weather that very day, rude carts, bespattered with
rustic mire, snuffed about by pigs, and roosted in by poultry, which
the Farmer, Death, had already set apart to be his tumbrils of
the Revolution. But that Woodman and that Farmer, though they work
unceasingly, work silently, and no one heard them as they went about
with muffled tread: the rather, forasmuch as to entertain any suspicion
that they were awake, was to be atheistical and traitorous."

}
msg_i = 0
print_speed = 2.5  -- chars per frame; can be fractional
print_speed_ctr = 0

function new_printer()
    local printer = {
        cur_x = 0,
        cur_y = 0,
        cur_str = nil,
        cur_pos = nil,
        cur_line = nil,
        color = 7,
        paused = false
    }

    function printer:print(s, color)
        if (color ~= nil) self.color = color
        if self.cur_str ~= nil then
            self.cur_str = self.cur_str..s
        else
            self.cur_str = s
            self.cur_pos = 1
            self.cur_line = 0
        end
    end

    function printer:scroll(h)
        if self.cur_y > 95 then
            memcpy(0x6000, 0x6000 + h*64, (108-h)*64)
        else
            self.cur_y += h
        end
        rectfill(0, 108-h, 128, 108, 0)
    end

    function printer:update()
        local c, p

        rectfill(0, 108, 128, 128, 1)
        if self.paused then
            print('-- more --', 86, 112, 6)
        end

        if btnp(5) and self.paused then
            self.paused = false
        end
        if self.paused then
            return
        end

        if self.cur_str ~= nil then
            c = sub(self.cur_str, self.cur_pos, self.cur_pos)
            if c == " " then
                p = self.cur_pos + 1
                while (p <= #self.cur_str) and
                        (sub(self.cur_str, p, p) ~= " ") do
                    p += 1
                end
                if (p - self.cur_pos) * 4 + self.cur_x > 127 then
                    self.cur_line +=1
                    if self.cur_line >= 14 then
                        self.paused = true
                        self.cur_line = 0
                    end
                    self:scroll(7)
                    self.cur_x = 0
                else
                    self.cur_x += 4
                end
            else
                print(c, self.cur_x, self.cur_y, self.color)
                self.cur_x += 4
            end
            self.cur_pos += 1
            if self.cur_pos > #self.cur_str then
                self:scroll(9)   -- end of paragraph scroll
                self.cur_x = 0
                self.cur_str = nil
                self.cur_pos = nil
                self.cur_line = nil
            end
        end
    end

    return printer
end

function _init()
    cls()
    printer = new_printer()
end

function _update()
    print_speed_ctr += print_speed
    while print_speed_ctr >= 1 do
      printer:update()
      print_speed_ctr -= 1
    end

    if printer.cur_str == nil and btnp(5) then
        printer:print(_t(msgs[msg_i+1]))
        msg_i = (msg_i + 1) % #msgs
    end
end

function _draw()
end
