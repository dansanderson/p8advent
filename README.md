# p8advent

This will eventually be an adventure game toolkit for the [Pico-8 virtual 
console](http://www.lexaloffle.com/pico-8.php). Right now it's just some data
format and workflow experiments. :)

Currently the only thing here are some experiments with packing text strings 
into cart data. The `p8advent` tool (see `tool.py`) uses a specially-marked 
Lua source file to create a Pico-8 cart with string literals extracted into 
the cart data region, packed using a given text packing library.

`textlib` was an early attempt at a dictionary-based packing library that 
focused on English words, inspired by methods used by old text adventure 
games. It stores both the code stream and the dictionary in cart data, and so
requires minimal RAM to access strings. In the context of Pico-8, it's not 
very satisfying: the compression rate for a long wordy text (_A Tale of Two
Cities_ by Charles Dickens) only compressed to about 75% the original size. 
Simply packing the 6-bit character set into 8-bit strings (a reasonable 
method not yet implemented here) would be as effective, so a fancier 
algorithm has to do better than this.

`lzwlib` uses the LZW compression algorithm with variable-width codes. All 
strings share the same dictionary to maximize packing, but are stored 
byte-aligned with headers so they can be accessed directly. This requires 
that the Lua code reconstruct the dictionary in RAM before accessing any 
strings. The Dickens test text compresses to 48% when using as much Lua RAM 
as possible for the largest possible dictionary. Capping the dictionary at
4,096 entries bumps this up to about 60% for this text.

Of course, ToTC is not a typical text corpus for a game, even a large 
text-based game. I'll need to make an actual game that uses a lot of text to 
demonstrate that fancy packing techniques are actually profitable. It seems 
likely that a game that uses both text and graphics and wants to store 
strings could simply use a bit stream of 6-bit characters.
