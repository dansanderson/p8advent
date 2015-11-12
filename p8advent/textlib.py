"""A text library.

TextLib stores a set of strings containing English text as compact binary
data. It can also generate Pico-8 Lua code capable of accessing a string given
the string's numeric ID (returned by the encoder method). The goal is to make it
easy to write Pico-8 games that use a large quantity of English text without
storing that text in the code region of the cart.

Strings are not encoded exactly. To save space when storing multi-word
English phrases, word spaces are not stored. The generated Lua code uses
rules about English phrases to calculate word spacing in the final string.

See p8advent.tool for code that generates a full Pico-8 cart that replaces
string literals in Lua source with string library IDs. To allow code to defer
string assembly until the last minute, the code must explicitly call the t(sid)
function (added during cart processing) to get the string value. String IDs
are encoded as strings, and can be concatenated. (sub() also works if you're
careful: each string ID is three characters long.)

TextLib uses a technique similar to the one used by old 8-bit text adventure
games. Words are encoded as two bytes: a prefix ID and a suffix ID. A prefix
is a fixed length that you set when you instantiate TextLib, typically 1 or 2.
Each prefix has a list of suffixes indexed by the suffix ID. The decoded word
is simply the prefix followed by the suffix. A string is a sequence of
literal non-word characters and word byte pairs. See as_bytes() for a
description of the complete binary representation.

(It's debatable whether this is the best way to compress a set of short English
phrases for a text game. It's also debatable whether a Pico-8 text game
benefits from storing its text in a compacted form in cart data vs. in the
code region. And of course making a text game in Pico-8 is a dubious endeavor
to begin with. I just wanted to play with this technique.)
"""

__all__ = ['TextLib', 'encode_pscii']

from collections import defaultdict
import re
import sys


_WORD = re.compile(r'[a-zA-Z\']+')


# A character set, which I'm going to call "pscii", consisting of all of the
# characters supported by TextLib. This corresponds to all of the characters
# supported by Pico-8 v0.1.3. Notable missing chars include: $ \ @ ` (I
# believe 0.1.4 will add support for "\".)
CHAR_TABLE = ' !"#%\'()*+,-./0123456789:;<=>?abcdefghijklmnopqrstuvwxyz[]^_{~}'


# A format pattern for the Lua code to inject. This expects a format key of
# "text_start_addr" equal to the RAM address where the text data begins.
#
# _c(o) converts a character code to a single-character string.
# _o(c) converts a single-character string to its character code (or nil).
#
# _t(sid) calculates the string with the given ID. It uses the string jump
# table to find the character and word codes for the string, then builds the
# result. If the next byte has its high bit set, then it and the following
# byte are the prefix and suffix ID, respectively, of a word in the word
# table. Otherwise it is a character code. For a word, it finds the prefix
# using the word jump table, reads the prefix at that location (of a fixed
# length encoded at pos 0), then scans a list of null-terminated suffixes to
# find the appropriate suffix.
#
# Spaces are added according to English punctuation rules:
#
# * a space between words: "word word"
# * a space after sentence ending punctuation and closing brackets if
#    followed by a word: !),.?:;]}
# * a space after a word if followed by opening brackets: ([{
# * double-quotes (") are treated as brackets, alternating between opening and
#    closing brackets
#
# Local variables in _t():
#
# * ta: The text data start absolute address.
# * r : The result accumulator.
# * sids : A list of string IDs encoded as a string of three-char segments.
# * sid : The (numeric, decoded) string ID.
# * sc : The sentence count.
# * sa : The address of the first byte of the sentence string.
#         This pointer is advanced during the sentence string loop.
# * sae : The address of the last byte of the sentence string + 1.
# * psa : The value at the sentence string pointer.
# * pi : The prefix index.
# * si : The suffix index.
# * wa : The address of the first byte of the prefix for the word.
# * pl : The prefix length.
# * pli : Prefix char index (0-based).
# * was : The address of the start of the word table.
# * lww : True if the last string part was a word.
# * lwep : True if the last string part was sentence-ending or
#           bracket-closing punctuation.
# * qt : True if the next double-quote is bracket-closing.
#
# TODO: Treat ~ (61) as a paragraph break, reset double-quote state.
CHAR_TABLE_LUA = re.sub(r'"', '"..\'"\'.."', CHAR_TABLE)
CHAR_TABLE_LUA = re.sub(r'{', '{{', CHAR_TABLE_LUA)
CHAR_TABLE_LUA = re.sub(r'}', '}}', CHAR_TABLE_LUA)
P8ADVENT_LUA_PAT = (
    '_ct="' + CHAR_TABLE_LUA + '"\n' +
    """
function _c(o) return sub(_ct,o+1,o+1) end
function _o(c)
 local i
 for i=1,#_ct do
  if sub(_ct,i,i)==c then return i-1 end
 end
 return 63
end
function _t(sids)
 local ta={text_start_addr}
 local sidsi,sid,r,sc,sa,sae,psa,pi,si,wa,pl,pli,was,lww,lwep,qt
 pl=peek(ta)
 sc=bor(shl(peek(ta+2),8),peek(ta+1))
 was=ta+bor(shl(peek(ta+sc*2+4),8),peek(ta+sc*2+3))
 r=''
 lww=false
 lwep=false
 qt=false
 for sidsi=1,#sids-2,3 do
  sid=bor(bor(_o(sub(sids,1,1)),
              shl(_o(sub(sids,2,2)),6)),
          shl(_o(sub(sids,3,3)),12))
  sa=ta+bor(shl(peek(ta+sid*2+4),8),peek(ta+sid*2+3))
  sae=ta+bor(shl(peek(ta+(sid+1)*2+4),8),peek(ta+(sid+1)*2+3))
  while sa<sae do
   psa=peek(sa)
   if band(psa,128)==128 then
    if (lww or lwep) r=r.." "
    pi=band(psa,127)
    si=peek(sa+1)
    wa=ta+bor(shl(peek(was+pi*2+1),8),peek(was+pi*2))
    for pli=0,pl-1 do
     if (peek(wa+pli) > 0) r=r.._c(peek(wa+pli))
    end
    wa=wa+pl
    while si>0 do
     while peek(wa)!=0 do wa+=1 end
     wa+=1
     si-=1
    end
    while peek(wa)!=0 do
     r=r.._c(peek(wa))
     wa+=1
    end
    sa+=1
    lww=true
    lwep=false
   else
    if ((lww and ((psa==2 and qt)or(psa==6)or(psa==56)or(psa==60))) or
        (lwep and psa==2 and not qt)) then
      r=r.." "
    end
    r=r.._c(psa)
    lww=false
    lwep=((psa==2 and qt)or(psa==7)or(psa==10)or(psa==12)or(psa==24)or
          (psa==25)or(psa==29)or(psa==57)or(psa==62))
    if (psa==2) qt=not qt
   end
   sa+=1
  end
 end
 return r
end
""")


class Error(Exception):
    """A base class for errors."""
    pass


class TooManyWordsForPrefixError(Error):
    """There were too many words with the same prefix.

    If this happens, increase the prefix length and try again.
    """
    pass


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
    ce = None
    try:
        for c in lower_s:
            ce = c
            result.append(CHAR_TABLE.index(c))
    except ValueError as e:
        sys.stderr.write('Character out of supported range: {}\n'.format(
            repr(ce)))
        raise
    return bytes(result)


class TextLib:
    def __init__(self, prefix_length=1):
        self._prefix_lst = list()
        self._word_lib = defaultdict(list)
        self._string_lib_map = dict()
        self._string_lib_lst = list()
        self._prefix_length = prefix_length

    def _encode_word(self, w):
        """Encodes a word, adding it to the library if necessary.

        The result is a prefix index followed by a lookup index for the suffix.

        If a prefix index grows beyond 127 or a suffix index grows beyond 255,
        we raise an exception. If this happens, increase the prefix length
        and try again. (A test with a very large document needed a 10-bit
        index with a 1-byte prefix, but an 8-bit index with a 2-byte prefix.)

        Args:
            w: The word.

        Returns:
            A bytestring, either <prefix_id><suffix_id> or a pscii bytestring if
            the word is shorter than the prefix length.
        """
        w = encode_pscii(w)
        if len(w) <= self._prefix_length:
            w += b'\x00' * (self._prefix_length - len(w))
            prefix = w
            suffix = b''
        else:
            prefix = w[:self._prefix_length]
            suffix = w[self._prefix_length:]
        if prefix not in self._word_lib:
            self._prefix_lst.append(prefix)
            prefix_id = len(self._prefix_lst) - 1
            if prefix_id > 127:
                raise TooManyWordsForPrefixError()
        else:
            prefix_id = self._prefix_lst.index(prefix)

        if suffix in self._word_lib[prefix]:
            suffix_id = self._word_lib[prefix].index(suffix)
        else:
            self._word_lib[prefix].append(suffix)
            suffix_id = len(self._word_lib[prefix]) - 1
            if suffix_id > 255:
                raise TooManyWordsForPrefixError()

        # Set high bit of prefix ID.
        prefix_id |= 128

        return bytes((prefix_id, suffix_id))

    def _encode_string(self, s):
        """Encodes the symbols of a string.

        Args:
            s: The string.

        Returns:
            The byte encoding for the string.
        """
        result = bytearray()
        s_i = 0
        while s_i < len(s):
            if s[s_i] == ' ':
                s_i += 1
                continue
            m = _WORD.match(s[s_i:])
            if not m:
                result.extend(encode_pscii(s[s_i]))
                s_i += 1
                continue
            result.extend(self._encode_word(m.group(0)))
            s_i += len(m.group(0))
        return result

    def _encode_string_id(self, id):
        """Encodes a string ID as three pscii characters.

        Args:
            id: The numeric ID, from 0 to 65535.

        Returns:
            The three-character string encoding of the ID.
        """
        # Add a special char to the table to make it 64 chars even.
        ct = CHAR_TABLE + '@'
        w1 = id & 63
        w2 = (id >> 6) & 63
        w3 = (id >> 12) & 63
        return ct[w1] + ct[w2] + ct[w3]

    def id_for_string(self, s):
        """Gets the ID for a string, adding it to the library if necessary.

        Args:
            s: The string.

        Returns:
            The string ID, encoded as a three-character pscii string.
        """
        s = re.sub(r'\s+', ' ', s)
        if s not in self._string_lib_map:
            self._string_lib_lst.append(self._encode_string(s))
            self._string_lib_map[s] = len(self._string_lib_lst) - 1
        return self._encode_string_id(self._string_lib_map[s])

    def as_bytes(self):
        """Dump the entire library in its byte encoding.

        The prefix length and table sizes are not encoded. It is expected
        that the generated access code will stay within expected ranges.
        TODO: This is dumb. I'm passing these values into the generated Lua,
        might as well store them with the bytes.

        0: The prefix length.
        1 - 2: The number of sentences, S, LSB first.
        3 - 2*S+2: The string jump table, each entry as an offset from pos 0,
          two bytes each, LSB first.
        2*S+3 - 2*S+4: The offset of the byte following the last byte of string
          S, LSB first. This serves two purposes: it allows the string reader
          to read two offsets from the jump table to get the length, and it's
          the offset of the word lookup table (W_addr).
        2*S+5 - ...: Encoded strings. If a byte has its high bit set, then it is
          a word prefix offset and the next byte is the suffix offset.
          Otherwise a given byte is a pscii code. Word spaces are omitted, and
          are up to the renderer to provide according to English punctuation
          rules.
        W_addr - W_addr+2*W-1: The prefix jump table, each entry as an offset
          from pos 0, two bytes each, LSB first.
        W_addr+2*W - ...: Word entries, null terminated. Each entry starts with
          the prefix (in pscii) followed by all of the suffixes (in pscii).
          Each suffix's final character has its high bit set.

        Returns:
            A bytearray.
        """
        longest_string_size = 0
        most_lookup_entries_count = 0
        total_lookup_entries_count = 0
        longest_suffix_size = 0

        string_offset_list = [0]
        string_data = bytearray()
        for s in self._string_lib_lst:
            string_data.extend(s)
            string_offset_list.append(len(string_data))
            if len(string_data) > longest_string_size:
                longest_string_size = len(string_data)
        string_table_offset = 3 + 2 * len(self._string_lib_lst) + 2
        string_jump_tbl = bytearray()
        for e in string_offset_list:
            v = string_table_offset + e
            if v >= 65536:
                raise TooManyWordsForPrefixError()
            string_jump_tbl.append(v & 255)
            string_jump_tbl.append(v >> 8)

        lookup_offset_list = [0]
        lookup_data = bytearray()
        for p in self._prefix_lst:
            lookup_data.extend(p)
            for suffix in self._word_lib[p]:
                lookup_data.extend(suffix)
                lookup_data.append(0)
                if len(suffix) > longest_suffix_size:
                    longest_suffix_size = len(suffix)
            lookup_offset_list.append(len(lookup_data))
            if len(self._word_lib[p]) > most_lookup_entries_count:
                most_lookup_entries_count = len(self._word_lib[p])
            total_lookup_entries_count += len(self._word_lib[p])
        lookup_table_offset = (3 + len(string_jump_tbl) + len(string_data) +
                               2 * len(self._prefix_lst))
        lookup_prefix_tbl = bytearray()
        # We don't need the offset past the last lookup:
        lookup_offset_list.pop()
        for e in lookup_offset_list:
            v = lookup_table_offset + e
            if v >= 65536:
                raise TooManyWordsForPrefixError()
            lookup_prefix_tbl.append(v & 255)
            lookup_prefix_tbl.append(v >> 8)

        num_of_strings = len(self._string_lib_lst)
        num_of_prefixes = len(self._prefix_lst)

        # TODO: remove these, or make them an official feature:
        print('DEBUG: num_of_strings = {}'.format(num_of_strings))
        print('DEBUG: num_of_prefixes = {}'.format(num_of_prefixes))
        print('DEBUG: longest_string_size = {}'.format(longest_string_size))
        print('DEBUG: longest_suffix_size = {}'.format(longest_suffix_size))
        print('DEBUG: most_lookup_entries_count = {}'.format(most_lookup_entries_count))
        print('DEBUG: total_lookup_entries_count = {}'.format(total_lookup_entries_count))
        print('DEBUG: total text lib size = {}'.format(len(string_jump_tbl) +
                                                       len(string_data) +
                                                       len(lookup_prefix_tbl) +
                                                       len(lookup_data)))

        return bytes(bytearray([self._prefix_length,
                                len(self._string_lib_lst) & 255,
                                len(self._string_lib_lst) >> 8]) +
                     string_jump_tbl +
                     string_data +
                     lookup_prefix_tbl +
                     lookup_data)

    def generate_lua(self, text_start_addr=0):
        """Generate the Lua code for accessing this TextLib.

        Args:
            text_start_addr: The starting address for the text bytes region.
        """
        return P8ADVENT_LUA_PAT.format(text_start_addr=text_start_addr)
