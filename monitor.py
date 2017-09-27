# Copyright (c) 2014-2017 esotericnonsense (Daniel Edgecumbe)
# Distributed under the MIT software license, see the accompanying
# file COPYING or https://opensource.org/licenses/mit-license.php

import datetime
import math
import curses
import asyncio
from decimal import Decimal

from macros import MIN_WINDOW_SIZE


class MonitorView(object):
    def __init__(self, client):
        self._client = client

        self._pad = None

        self._visible = False

        self._lock = asyncio.Lock()
        self._bestblockhash = None
        self._bestblockheader = None  # raw json blockheader
        self._bestblock = None  # raw json block
        self._bestcoinbase = None  # raw json tx
        self._dt = None

        self._window_size = MIN_WINDOW_SIZE

    def _draw(self):
        # TODO: figure out window width etc.

        if self._pad is not None:
            self._pad.clear()
        else:
            self._pad = curses.newpad(20, 100)

        if self._bestblockheader:
            bbh = self._bestblockheader
            self._pad.addstr(0, 1, "Height: {: 8d}".format(bbh["height"]))
            self._pad.addstr(0, 36, bbh["hash"])

        if self._bestblock:
            bb = self._bestblock
            self._pad.addstr(1, 1, "Size: {: 8d} bytes               Weight: {: 8d} WU".format(
                bb["size"],
                bb["weight"]
            ))

            self._pad.addstr(1, 64, "Block timestamp: {}".format(
                datetime.datetime.utcfromtimestamp(bb["time"]),
            ))

            if self._dt:
                stampdelta = int(
                    (self._dt - datetime.datetime.utcfromtimestamp(bb["time"]))
                    .total_seconds())

                if stampdelta > 3600*3:  # probably syncing
                    stampdelta_string = "             (syncing)"

                elif stampdelta > 0:
                    m, s = divmod(stampdelta, 60)
                    h, m = divmod(m, 60)
                    d, h = divmod(h, 24)
                    stampdelta_string = "({:d}d {:02d}:{:02d}:{:02d} by stamp)".format(d,h,m,s)

                else:
                    stampdelta_string = "     (stamp in future)"

                self._pad.addstr(2, 64, "Age:          {}".format(
                    stampdelta_string))

            self._pad.addstr(2, 1, "Transactions: {} ({} bytes/tx, {} WU/tx)".format(
                len(bb["tx"]),
                bb["size"] // len(bb["tx"]),
                bb["weight"] // len(bb["tx"]),
            ))

            if self._bestcoinbase:
                bcb = self._bestcoinbase
                reward = sum(vout["value"] for vout in bcb["vout"])

                # TODO: if chain is regtest, this is different
                halvings = bb["height"] // 210000
                block_subsidy = Decimal(50 * (0.5 ** halvings))

                total_fees = Decimal(reward) - block_subsidy

                self._pad.addstr(4, 1, "Block reward: {:.6f} BTC".format(
                    reward))

                if len(bb["tx"]) > 1:
                    if reward > 0:
                        fee_pct = total_fees * 100 / Decimal(reward)
                    else:
                        fee_pct = 0
                    mbtc_per_tx = (total_fees / (len(bb["tx"]) - 1)) * 1000

                    # 80 bytes for the block header.
                    total_tx_size = bb["size"] - 80 - bcb["size"]
                    if total_tx_size > 0:
                        sat_per_kb = ((total_fees * 1024) / total_tx_size) * 100000000
                    else:
                        sat_per_kb = 0
                    self._pad.addstr(4, 34, "Fees: {: 8.6f} BTC ({: 6.2f}%, avg {: 6.2f} mBTC/tx, ~{: 7.0f} sat/kB)".format(total_fees, fee_pct, mbtc_per_tx, sat_per_kb))

            self._pad.addstr(6, 1, "Diff: {:,}".format(
                int(bb["difficulty"]),
            ))
            self._pad.addstr(7, 1, "Chain work: 2**{:.6f}".format(
                math.log(int(bb["chainwork"], 16), 2),
            ))

        self._draw_pad_to_screen()

    def _draw_pad_to_screen(self):
        maxy, maxx = self._window_size
        if maxy < 8 or maxx < 3:
            return # Can't do it

        self._pad.refresh(0, 0, 4, 0, min(maxy-3, 24), min(maxx-1, 100))

    async def draw(self):
        with await self._lock:
            self._draw()

    async def on_bestblockhash(self, key, obj):
        try:
            bestblockhash = obj["result"]
        except KeyError:
            return

        draw = False
        with await self._lock:
            if bestblockhash != self._bestblockhash:
                draw = True
                self._bestblockhash = bestblockhash

                j = await self._client.request("getblockheader", [bestblockhash])
                self._bestblockheader = j["result"]

                j = await self._client.request("getblock", [bestblockhash])
                self._bestblock = j["result"]

                j = await self._client.request("getrawtransaction", [j["result"]["tx"][0], 1])
                self._bestcoinbase = j["result"]

        if draw and self._visible:
            await self.draw()

    async def on_tick(self, dt):
        with await self._lock:
            self._dt = dt

        if self._visible:
            await self.draw()

    async def on_mode_change(self, newmode):
        if newmode != "monitor":
            self._visible = False
            return

        self._visible = True
        await self.draw()

    async def on_window_resize(self, y, x):
        # At the moment we ignore the x size and limit to 100.
        self._window_size = (y, x)
        if self._visible:
            await self.draw()