"""The main routines for the command-line tool.

This tool processes a Lua source file into a Pico-8 cart. It adds a simple
syntax rule for string literals: If a string literal is immediately preceded
by a star (*), the string is added to a text lib data structure, and the
string literal is replaced with an encoded string ID (also a string). To get
the original string, the Lua code must call the _t() function (added to the
Lua code by the tool) and pass it the string ID. For example:

  function _update()
    msg = *"check it out everyone it's the apocalypse!"
    print(_t(msg))
  end

This becomes:

  function _update()
    msg = "   "
    print(_t(msg))
  end
  function _t(sid)
    ...
  end

The string data is moved into the graphics region of the Pico-8 cart. The _t()
function uses the encoded ID to locate and unpack the string.
"""

__all__ = ['main']

import argparse
import textwrap

from pico8.game import game
from pico8.lua import lexer

from . import lzwlib


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
        '--lua', type=str, required=True,
        help='the annotated Lua code for the game')
    parser.add_argument(
        '--startaddr', type=int, default=TEXT_START_ADDR,
        help='the Pico-8 cart address to put the text data')
    parser.add_argument(
        '--endaddr', type=int, default=TEXT_END_ADDR,
        help='the Pico-8 cart address the the text data must end; if the text'
             'data is too long, this tool reports an error')
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

    my_textlib = lzwlib.LzwLib(start_addr=args.startaddr, end_addr=args.endaddr)

    saw_star = False
    for i, token in enumerate(my_lexer._tokens):
        if token.matches(lexer.TokSymbol('*')):
            saw_star = True
        elif token.matches(lexer.TokString) and saw_star:
            sid = my_textlib.id_for_string(token.value)
            my_lexer._tokens[i-1] = lexer.TokSpace('')
            my_lexer._tokens[i] = lexer.TokString(sid)
            saw_star = False
        else:
            saw_star = False

    textlib_lua = my_textlib.generate_lua()
    my_lexer.process_lines(l+'\n' for l in textlib_lua.split('\n'))

    my_game.lua._lexer = my_lexer
    my_game.lua._parser.process_tokens(my_game.lua._lexer.tokens)

    text_bytes = my_textlib.as_bytes()
    my_game.write_cart_data(text_bytes, args.startaddr)

    with open(game_fname, 'w') as outstr:
        my_game.to_p8_file(outstr, filename=game_fname)

    return 0
