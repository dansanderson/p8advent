"""The main routines for the command-line tool."""

__all__ = ['main']

import argparse
import textwrap

from pico8.game import game
from pico8.lua import lexer

from . import textlib


# Depending on the text, this may need to be set to 2 to balance the number
# of prefixes and the number of suffixes per prefix.
TEXT_PREFIX_LENGTH = 1

# To preserve a portion of the gfx region, use 512 * number of sprite rows.
TEXT_START_ADDR = 0

# To preserve the song/sfx region, use 0x3100.
TEXT_END_ADDR = 0x4300


def _get_argparser():
    """Builds and returns the argument parser."""
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage='%(prog)s [--help] --lua <game.lua>',
        description=textwrap.dedent('''
        '''))
    parser.add_argument(
        '--lua', type=str,
        help='the annotated Lua code for the game')
    return parser


def main(orig_args):
    arg_parser = _get_argparser()
    args = arg_parser.parse_args(args=orig_args)

    assert args.lua.endswith('.lua')
    game_fname = args.lua[:-len('.lua')] + '.p8'

    my_game = game.Game.make_empty_game(filename=game_fname)
    my_lexer = lexer.Lexer(version=4)
    with open(args.lua) as lua_fh:
        my_lexer.process_lines(lua_fh)

    my_textlib = textlib.TextLib(prefix_length=TEXT_PREFIX_LENGTH)

    for i, token in enumerate(my_lexer._tokens):
        if token.matches(lexer.TokString):
            sid = my_textlib.id_for_string(token.value)
            my_lexer._tokens[i] = lexer.TokNumber(str(sid))

    textlib_lua = my_textlib.generate_lua(text_start_addr=TEXT_START_ADDR)
    my_lexer.process_lines(l+'\n' for l in textlib_lua.split('\n'))

    my_game.lua._lexer = my_lexer
    my_game.lua._parser.process_tokens(my_game.lua._lexer.tokens)

    text_bytes = my_textlib.as_bytes()
    if TEXT_START_ADDR + len(text_bytes) > TEXT_END_ADDR:
        raise ValueError('Text is too large to fit in the requested memory '
                         'region: {} bytes is larger than {}-{}'.format(
            len(text_bytes), TEXT_START_ADDR, TEXT_END_ADDR
        ))
    # TODO: generalize this into game class:
    memmap = ((0x0,0x2000,my_game.gfx._data),
              (0x2000,0x3000,my_game.map._data),
              (0x3000,0x3100,my_game.gff._data),
              (0x3100,0x3200,my_game.music._data),
              (0x3200,0x4300,my_game.sfx._data))
    for start_a, end_a, data in memmap:
        if (TEXT_START_ADDR > end_a or
            TEXT_START_ADDR + len(text_bytes) < start_a):
            continue
        data_start_a = (TEXT_START_ADDR - start_a
                        if TEXT_START_ADDR > start_a
                        else 0)
        data_end_a = (TEXT_START_ADDR + len(text_bytes) - start_a
                      if TEXT_START_ADDR + len(text_bytes) < end_a
                      else end_a)
        text_start_a = (0 if TEXT_START_ADDR > start_a
                        else start_a - TEXT_START_ADDR)
        text_end_a = (len(text_bytes)
                      if TEXT_START_ADDR + len(text_bytes) < end_a
                      else -(TEXT_START_ADDR + len(text_bytes) - end_a))
        data[data_start_a:data_end_a] = text_bytes[text_start_a:text_end_a]

    with open(game_fname, 'w') as outstr:
        my_game.to_p8_file(outstr, filename=game_fname)

    return 0
