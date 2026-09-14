"""Run with: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest
from pathlib import Path

_test_dir = tempfile.TemporaryDirectory()
os.environ['STADIA_DB_PATH'] = str(Path(_test_dir.name) / 'test.db')
os.environ.pop('DATABASE_URL', None)
import chess_db as db
import counter_chess as counter
from chess_tokens import make_seat_token
from streamlit.testing.v1 import AppTest

db.DATABASE_URL = ''

class RestoreTests(unittest.TestCase):
    def setUp(self):
        db.init_db()

    def test_home_has_both_games(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'streamlit_app.py')).run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.radio(key='new_game_variant').options), 2)

    def test_both_games_load_and_accept_moves(self):
        for variant, count in [(db.VARIANT_CLASSIC, 64), (db.VARIANT_COUNTER, 80)]:
            with self.subTest(variant=variant):
                gid = db.create_game('White', 'Black', time_control='relaxed', variant=variant)
                db.join_black(gid, 'Black')
                db.start_game(gid)
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'streamlit_app.py'))
                app.query_params['seat'] = make_seat_token(gid, 'white', 'DEV-ONLY-CHANGE-ME')
                app.query_params['lang'] = 'IT'
                app.run()
                self.assertFalse(app.exception)
                self.assertTrue(app.get('component_instance'))
                # A browser event is handled once, even across repeated polls.
                key = f'stadia_board_v087_{gid}_white'
                app.session_state[key] = {'move': 'e2e4', 'nonce': 'test-white'}
                app.run()
                self.assertEqual(len(db.get_moves(gid)), 1)
                app.run()
                self.assertEqual(len(db.get_moves(gid)), 1)
                db.make_move(gid, 'e7e5')
                app.checkbox(key=f'simple_board_{gid}_white').check().run()
                self.assertFalse(app.exception)
                squares = [b for b in app.button if b.key and b.key.startswith('svsq_')]
                self.assertEqual(len(squares), count)
                # Selection and destination clicks on the fallback submit a move.
                next(b for b in squares if b.help == 'a2').click().run()
                next(b for b in app.button if b.help == 'a3').click().run()
                self.assertFalse(app.exception)
                self.assertEqual(len(db.get_moves(gid)), 3)
                self.assertEqual(db.get_game(gid)['variant'], variant)

    def test_transparent_bishop_and_interceptor(self):
        board = counter.Board(board={(0,0):'K',(9,7):'k',(2,2):'T',(3,3):'P'},castling='')
        moves = {m.uci() for m in board.legal_moves}
        self.assertIn('c3e5', moves)
        self.assertIn('c3f6', moves)
        self.assertNotIn('c3g7', moves)
        board.board[(1,2)] = 'i'
        self.assertNotIn('c3e5', {m.uci() for m in board.legal_moves})
        board = counter.Board(board={(0,0):'K',(9,7):'k',(4,3):'I'},castling='')
        moves = [m for m in board.legal_moves if m.src == (4,3)]
        self.assertEqual(len(moves), 8)

if __name__ == '__main__':
    unittest.main()
