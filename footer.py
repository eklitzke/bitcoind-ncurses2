# Copyright (c) 2014-2017 esotericnonsense (Daniel Edgecumbe)
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/licenses/mit-license.php

import curses

from macros import MODES, MIN_WINDOW_SIZE


class FooterView(object):
    def __init__(self):
        self._pad = None

        self._mode = None
        self._dt = None

        self._callbacks = set()

        self._window_size = MIN_WINDOW_SIZE

    def add_callback(self, callback):
        self._callbacks.add(callback)

    def draw(self):
        # TODO: figure out window width etc.
        if self._pad is None:
            self._pad = curses.newpad(2, 100)
        else:
            self._pad.clear()

        CYELLOW = curses.color_pair(5)
        CREVERSE = curses.A_REVERSE

        x = 1
        for mode_string in MODES:
            first_char, rest = mode_string[0], mode_string[1:]
            modifier = curses.A_BOLD
            if self._mode == mode_string:
                # first_char = first_char.upper()
                modifier += CREVERSE
            self._pad.addstr(0, x, first_char, modifier + CYELLOW)
            self._pad.addstr(0, x+1, rest, modifier)
            x += len(mode_string) + 4

        if self._dt:
            self._pad.addstr(0, 81, self._dt.isoformat(timespec="seconds")[:19])

        self._draw_pad_to_screen()

    def _draw_pad_to_screen(self):
        maxy, maxx = self._window_size
        if maxy < 5 or maxx < 3:
            # Can't do it
            return

        self._pad.refresh(0, 0, maxy-2, 0, maxy, min(maxx-1, 100))

    async def on_mode_change(self, newmode, seek=None):
        if seek is not None:
            assert newmode is None
            if self._mode is None:
                return
            idx = MODES.index(self._mode)
            idx = (idx + seek) % len(MODES)
            newmode = MODES[idx]

        self._mode = newmode
        self.draw()

        for callback in self._callbacks:
            await callback(newmode)

    async def on_tick(self, dt):
        self._dt = dt
        self.draw()

    async def on_window_resize(self, y, x):
        # At the moment we ignore the x size and limit to 100.
        if y > self._window_size[0] and self._pad:
            self._pad.clear()
            self._draw_pad_to_screen()

        self._window_size = (y, x)
        self.draw()