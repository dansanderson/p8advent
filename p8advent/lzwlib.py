"""An LZW-based string packer.

LzwLib stores a set of strings as compressed binary data. It can also
generate Pico-8 Lua code capable of accessing a string given a string's ID (
returned by the encoder method). The goal is to make it easy to write Pico-8
games that use a large quantity of English text without storing that text in
the code region of the cart.

All strings added to the data structure contribute to a single decoder
dictionary. The Lua client generates this dictionary from the complete LZW
data the first time a string is accessed.

The ID of a string is a 16-bit value equal to the address of the compressed
data for the string in memory. The compressed string is stored as two bytes
representing its compressed size (LSB first) followed by the codes. The
ID is returned encoded as a string of 6-bit characters codes in the "pscii"
character set.

This is meant to be a drop-in replacement for TextLib, which was a silly idea
that never compressed very well. Unlike TextLib, LzwLib does not distinguish
between word and non-word characters, and preserves all characters including
spaces, with the exception of newlines which are converted to single spaces.
"""

from collections import OrderedDict
import re

__all__ = ['LzwLib', 'encode_pscii']


# A character set, which I'm going to call "pscii", consisting of all of the
# characters supported by TextLib. This corresponds to all of the characters
# supported by Pico-8 v0.1.3. Notable missing chars include: $ \ @ ` (I
# believe 0.1.4 will add support for "\".)
CHAR_TABLE = ' !"#%\'()*+,-./0123456789:;<=>?abcdefghijklmnopqrstuvwxyz[]^_{~}'

# For string-encoding IDs, add a character to make it an even 64 chars.
CHAR_TABLE_FOR_SID = CHAR_TABLE + '@'

# The Lua code for a string unpacker.
#
# _t(sid) unpacks and returns one or more strings. sid is a string containing
#  one or more string-encoded string IDs, three chars each. If sid contains
# multiple three-char IDs, the return value is each of those strings
# concatenated. This allows for the original Lua source to concatenate string
# IDs as if they are the original string, then call _t() at the last moment
# to unpack the aggregate result.
#
# _c(o) converts a character code to a single-character string.
# _o(c) converts a single-character string to its character code (or nil).
# _tlinit is true after the first call to _t().
# _tladdr is the starting address of the compressed data.
# _ct is the character table.
#
# (Note: Unlike TextLib's P8ADVENT_LUA_PAT, this is not a format pattern.)
P8ADVENT_LUA = """
_tl={a=nil,t=nil,d=nil,w=nil}
function _tl:c(o) return sub(_tl.t,o+1,o+1) end
function _tl:o(c)
 local i
 for i=1,#self.t do
  if sub(self.t,i,i)==c then return i-1 end
 end
 return 63
end
function _t(s)
 local p,r,c,n,i,a,l,bp,w,b
 local tid
 if _tl.d == nil then
  _tl.d={}
  n=bor(peek(_tl.a),shl(peek(_tl.a+1),8))
  a=_tl.a+2
  while n>0 do
   p=nil
   i=bor(peek(a),shl(peek(a+1),8))
   a+=5
   bp=0
   while i>0 do
    c=0
    w=_tl.w
    for bi=1,w do
     b=band(shr(peek(a),bp),1)
     c=bor(c,shl(b,bi-1))
     bp+=1
     if bp==8 then
      a+=1
      bp=0
     end
    end
    r=nil
    if c<=(#_tl.t-1) then
     r=_tl:c(c)
    elseif _tl.d[c-#_tl.t+1]~=nil then
     r=_tl.d[c-#_tl.t+1]
    end
    if p~=nil and #_tl.d+#_tl.t<tl.mt then
     if r~=nil then
      _tl.d[#_tl.d+1]=p..sub(r,1,1)
     else
      _tl.d[c-#_tl.t+1]=p..sub(p,1,1)
      r=_tl.d[c-#_tl.t+1]
     end
     if #_tl.d+#_tl.t==(2^_tl.w-1) then
      _tl.w+=1
     end
    end
    p=r
    i-=1
   end
   n-=1
   if bp~=0 then
    a+=1
    bp=0
   end
  end
 end

 r=''
 for i=1,#s,3 do
  a=bor(bor(_tl:o(sub(s,i,i)),
             shl(_tl:o(sub(s,i+1,i+1)),6)),
         shl(_tl:o(sub(s,i+2,i+2)),12))
  l=bor(peek(a),shl(peek(a+1),8))
  a+=2
  tid=bor(peek(a),shl(peek(a+1),8))
  a+=2
  _tl.w=peek(a)
  a+=1
  bp=0
  while l>0 do
   c=0
   w=_tl.w
   for bi=1,w do
    b=band(shr(peek(a),bp),1)
    c=bor(c,shl(b,bi-1))
    bp+=1
    if bp==8 then
     a+=1
     bp=0
    end
   end
   l-=1
   if c<=(#_tl.t-1) then
    r=r.._tl:c(c)
   else
    r=r.._tl.d[c-#_tl.t+1]
   end
   tid+=1
   if tid==(2^_tl.w) then
    _tl.w+=1
   end
  end
 end
 return r
end
"""

LZW_STARTING_WIDTH = 7

MAX_TABLE_ENTRY_COUNT = 4096


def _generate_lua(start_addr):
    """Generate the Lua code for the string unpacker.

    Args:
        start_addr: The starting address of the data region.

    Returns:
        The Lua code, as a string.
    """
    # Remove leading spaces to reduce char footprint.
    lua = re.sub(r'\n +', '\n', P8ADVENT_LUA)

    return ('{}\n_tl.t="{}"\n_tl.a={}\n_tl.w={}\n_tl.mt={}\n'.format(
        lua,
        re.sub(r'"', '"..\'"\'.."', CHAR_TABLE),
        start_addr,
        LZW_STARTING_WIDTH,
        MAX_TABLE_ENTRY_COUNT))


class Error(Exception):
    """A base class for errors."""
    pass


class CharOutOfRange(Error):
    """A character was in a string that is not supported by pscii."""
    def __init__(self, *args, **kwargs):
        self.char = kwargs.get('char')
        self.pos = kwargs.get('pos')
        super().__init__(*args, **kwargs)

    def __str__(self):
        return ('Character out of range: {}, pos:{}'.format(
            repr(self.char),
            self.pos))


class TooMuchDataError(Error):
    """The compressed data does not fit in the given cart data range.
    """
    def __init__(self, msg):
        self._msg = msg

    def __str__(self):
        return 'Too much data: {}'.format(self._msg)


def encode_pscii(s):
    """Encode an ASCII string as a bytestring in terms of the character table.

    Args:
        s: The Python string to encode.

    Returns:
        The bytestring of indexes into CHAR_TABLE.

    Raises:
        ValueError: The string contains a character not in CHAR_TABLE.
    """
    result = bytearray()
    lower_s = s.lower()
    i = c = None
    try:
        for i, c in enumerate(lower_s):
            result.append(CHAR_TABLE.index(c))
    except ValueError as e:
        raise CharOutOfRange(c, i)
    return bytes(result)


class LzwLib:
    def __init__(self, start_addr=0, end_addr=0x4300):
        """Initializer.

        You can use arguments to customize the addresses and maximum memory
        ranges for the compressed data in the cart and for the lookup
        dictionary in RAM.

        Args:
            start_addr: The Pico-8 cart data starting address for the data.
            end_addr: The Pico-8 cart data ending address for the data + 1.
        """
        self._start_addr = start_addr
        self._end_addr = end_addr

        self._string_id_map = dict()
        self._data = bytearray()
        self._dict = OrderedDict(
            (CHAR_TABLE[i], i) for i in range(len(CHAR_TABLE)))

        self._code_width = LZW_STARTING_WIDTH
        self._code_bit_pos = 0
        self._code_buffer = None

    def id_for_string(self, s):
        s = re.sub(r'\s+', ' ', s.lower())
        if s not in self._string_id_map:
            # TODO: dict length - 1?
            expected_table_id = len(self._dict)
            expected_code_width = self._code_width

            self._code_buffer = bytearray()
            self._code_bit_pos = 0
            sid = self._start_addr + 2 + len(self._data)
            start_i = 0
            code_count = 0
            while start_i < len(s):
                end_i = start_i + 1
                while end_i < len(s) and s[start_i:end_i] in self._dict:
                    end_i += 1
                created_new_entry = None
                if s[start_i:end_i] not in self._dict:
                    # (Condition may or may not be false at the end of the
                    # string, so we check.)
                    if len(self._dict) < MAX_TABLE_ENTRY_COUNT:
                        self._dict[s[start_i:end_i]] = len(self._dict)
                        created_new_entry = self._dict[s[start_i:end_i]]
                    end_i -= 1

                code = self._dict[s[start_i:end_i]]
                for i in range(self._code_width):
                    if self._code_bit_pos == 0:
                        self._code_buffer.append(0)
                    self._code_buffer[-1] |= (code & 1) << self._code_bit_pos
                    code >>= 1
                    self._code_bit_pos = (self._code_bit_pos + 1) % 8

                if (created_new_entry is not None and
                    created_new_entry == (2**self._code_width - 1)):
                    self._code_width += 1

                code_count += 1
                start_i = end_i

            self._data.append(code_count & 255)
            self._data.append(code_count >> 8)
            self._data.append(expected_table_id & 255)
            self._data.append(expected_table_id >> 8)
            self._data.append(expected_code_width)
            self._data.extend(self._code_buffer)

            encoded_sid = (CHAR_TABLE_FOR_SID[sid & 63] +
                           CHAR_TABLE_FOR_SID[(sid >> 6) & 63] +
                           CHAR_TABLE_FOR_SID[(sid >> 12) & 63])
            self._string_id_map[s] = encoded_sid

        return self._string_id_map[s]

    def as_bytes(self):
        """Get the binary data for the packed text.

        Returns:
            The data, as a bytearray.

        Raises:
            TooMuchDataError: The given strings do not fit into the memory
              ranges given to __init__.
        """
        string_count = len(self._string_id_map)
        data = (bytearray([string_count & 255, string_count >> 8]) +
                self._data)

        total_string_size = sum(len(k) for k in self._string_id_map.keys())
        compressed_data_size = len(data)
        lookup_table_count = len(self._dict)
        lookup_table_size = sum(len(k) for k in self._dict.keys())
        print(
            'DEBUG: unique string count: {string_count}\n'
            'DEBUG: total unique string size: {total_string_size}\n'
            'DEBUG: lookup table entry count: {lookup_table_count}\n'
            'DEBUG: compressed data size: {compressed_data_size}\n'
            'DEBUG: lookup table size: {lookup_table_size}\n'
            .format(**locals()))

        if len(data) > (self._end_addr - self._start_addr):
            raise TooMuchDataError(
                'compressed data is too large: {} bytes do not fit between '
                'addresses {} and {}'.format(
                    len(data), self._start_addr, self._end_addr))
        return data

    def generate_lua(self):
        """Generate the Lua code for accessing this LzwLib.

        Returns:
            The Lua code.
        """
        return _generate_lua(self._start_addr)
