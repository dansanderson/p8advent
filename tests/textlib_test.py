import unittest

from p8advent import textlib


class TestTextLib(unittest.TestCase):
    def setUp(self):
        self.tl = textlib.TextLib(prefix_length=2)

    def test_encode_pscii(self):
        self.assertEqual(b'\x1e\x1f\x20\x21\x22\x23\x0f\x10\x11',
                         textlib.encode_pscii('abcDEF123'))

    def test_encode_word(self):
        result = self.tl._encode_word('aardvark')
        self.assertEqual(b'\x80\x00', result)
        result = self.tl._encode_word('aaron')
        self.assertEqual(b'\x80\x01', result)
        result = self.tl._encode_word('baron')
        self.assertEqual(b'\x81\x00', result)

    def test_encode_word_shorter_than_prefix(self):
        result = self.tl._encode_word('a')
        self.assertEqual(b'\x80\x00', result)

    def test_encode_word_too_many_prefixes(self):
        try:
            for a in range(ord('a'), ord('z')):
                for b in range(ord('a'), ord('z')):
                    w = chr(a) + chr(b) + 'x'
                    self.tl._encode_word(w)
            self.fail()
        except textlib.TooManyWordsForPrefixError:
            pass

    def test_encode_word_too_many_suffixes(self):
        try:
            for a in range(ord('a'), ord('z')):
                for b in range(ord('a'), ord('z')):
                    w = 'xx' + chr(a) + chr(b)
                    self.tl._encode_word(w)
            self.fail()
        except textlib.TooManyWordsForPrefixError:
            pass

    def test_encode_string(self):
        result = self.tl._encode_string('aardvark aaron baron')
        self.assertEqual(b'\x80\x00\x80\x01\x81\x00', result)

        result = self.tl._encode_string('"Aardvark? Aaron, baron."')
        self.assertEqual(b'\x02\x80\x00\x1d\x80\x01\x0a\x81\x00\x0c\x02',
                         result)

    def test_id_for_string(self):
        result = self.tl.id_for_string('aardvark aaron baron')
        self.assertEqual(0, result)

        result = self.tl.id_for_string('"Aardvark? Aaron, baron."')
        self.assertEqual(1, result)

        result = self.tl.id_for_string('aardvark aaron baron')
        self.assertEqual(0, result)

    def test_as_bytes(self):
        self.tl.id_for_string('aardvark aaron baron')
        self.tl.id_for_string('"Aardvark? Aaron, baron."')

        result = self.tl.as_bytes()
        expected = (b'\x02\x02\x00' +
                    b'\x09\x00\x0f\x00\x1a\x00' +  # string jump table
                    b'\x80\x00\x80\x01\x81\x00' +  # string data
                    b'\x02\x80\x00\x1d\x80\x01\x0a\x81\x00\x0c\x02' +
                    b'\x1e\x00\x2b\x00' +  # prefix jump table
                    b'\x1e\x1e\x2f\x21\x33\x1e\x2f\x28\x00' +  # lookup data
                    b'\x2f\x2c\x2b\x00' +
                    b'\x1f\x1e\x2f\x2c\x2b\x00')
        self.assertEqual(expected, result)

    def test_generate_lua(self):
        self.tl.id_for_string('aardvark aaron baron')
        self.tl.id_for_string('"Aardvark? Aaron, baron."')

        result = self.tl.generate_lua(text_start_addr=512)
        self.assertIn('local ta=512\n', result)


if __name__ == '__main__':
    unittest.main()
