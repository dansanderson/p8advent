"""A text library."""

__all__ = ['TextLib', 'encode_pscii']

from collections import defaultdict
import re


_WORD = re.compile(r'[a-zA-Z\']+')


# A character set, which I'm going to call "pscii", consisting of all of the
# characters supported by TextLib. This corresponds to all of the characters
# supported by Pico-8 v0.1.3. Notable missing chars include: $ \ @ ` (I
# believe 0.1.4 will add support for "\".)
CHAR_TABLE = ' !"#%\'()*+,-./0123456789:;<=>?abcdefghijklmnopqrstuvwxyz[]^_{~}'


# A format pattern for the Lua code to inject. Format keys include:
#   text_start_addr: the RAM address where the text data begins
#   word_start_addr: the RAM address where the word lookup data begins
#   prefix_length: the prefix length
CHAR_TABLE_LUA = re.sub(r'"', '"..\'"\'.."', CHAR_TABLE)
CHAR_TABLE_LUA = re.sub(r'{', '{{', CHAR_TABLE_LUA)
CHAR_TABLE_LUA = re.sub(r'}', '}}', CHAR_TABLE_LUA)
P8ADVENT_LUA_PAT = (
    '_ct="' +
    CHAR_TABLE_LUA +
    '"\n_ta={text_start_addr}' +
    '''
function _c(o) return sub(_ct,o+1,o+1) end
function t(sid)
 local r,sa,sae,pi,si,wa,pl,pli,was
 pl=peek(_ta)
 sc=bor(shl(peek(_ta+2),8),peek(_ta+1))
 was=_ta+bor(shl(peek(_ta+sc*2+4),8),peek(_ta+sc*2+3))
 r=''
 sa=_ta+bor(shl(peek(_ta+sid*2+4),8),peek(_ta+sid*2+3))
 sae=_ta+bor(shl(peek(_ta+(sid+1)*2+4),8),peek(_ta+(sid+1)*2+3))
 while sa<sae do
  if band(peek(sa),128)==128 then
   pi=band(peek(sa),127)
   si=peek(sa+1)
   wa=_ta+bor(shl(peek(was+pi*2+1),8),peek(was+pi*2))
   for pli=0,pl-1 do
    r=r.._c(peek(wa+pli))
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
  else
   r=r.._c(peek(sa))
  end
  sa+=1
 end
 return r
end
''')


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
    for c in lower_s:
        result.append(CHAR_TABLE.index(c))
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
            return w
        prefix = w[:self._prefix_length]
        suffix = w[self._prefix_length:]
        print('DEBUG: prefix_length={} prefix={} suffix={}'.format(
            self._prefix_length, list(prefix), list(suffix)))
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

    def id_for_string(self, s):
        """Gets the ID for a string, adding it to the library if necessary.

        Args:
            s: The string.

        Returns:
            The string ID.
        """
        s = re.sub(r' +', ' ', s)
        if s not in self._string_lib_map:
            self._string_lib_lst.append(self._encode_string(s))
            self._string_lib_map[s] = len(self._string_lib_lst) - 1
        return self._string_lib_map[s]

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
