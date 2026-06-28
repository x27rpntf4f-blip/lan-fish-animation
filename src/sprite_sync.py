"""
SpriteSyncManager —— 网络精灵分片接收与重组。

为什么需要它：
- 单帧 PNG 可能几十 KB，而 UDP 报文（mtu ~1500）单包不超过 ~1400B。
- 因此发送端 (main.py `_send_sprite_data_async`) 把每帧切成 460 字节的 chunk
  (`CHUNK_SIZE = 460`，对应 main 模块的常量)，逐个用 SPRITE_CHUNK 消息发出。
- 接收端必须按 (sprite_name, frame_index) 收集所有 chunk，重组成完整 PNG
  字节流并落盘，才能让 SpriteManager 重新扫描到。

可靠性策略：
- 单一帧内的所有 chunk 必须 *全部* 收齐才落盘（按位掩码判定）。
- _pending 字典中保留未完成帧；超 MAX_PENDING 时丢弃最早条目，防止内存爆炸。
- 落盘后 main 调 sprite_mgr._scan_sprites_dir()，本地即可使用新 type。
"""

import os
import struct


class SpriteSyncManager:
    """
    接收端精灵分片重组器。

    状态：
    - self._pending: dict  {(name, frame_index) -> entry}
        entry = {
            "total":   int,                # 期望的 chunk 总数
            "received": int,               # 已收 chunk 索引的位掩码
            "chunks": {idx: bytes, ...},   # 实际收到的数据
        }

    接口：
    - feed_chunk(info) : 处理一个 SPRITE_CHUNK 消息；帧完整返回 True。
    - pending_count()  : 当前未完成帧数（用于监控/调试）。
    """

    # 同时维护的未完成帧上限。超过则按插入顺序淘汰最早的条目。
    MAX_PENDING = 32

    def __init__(self, sprites_dir):
        """
        参数：
        - sprites_dir : 本地素材根目录（一般指向 SpriteManager.SPRITE_DIR），
                        重组完成的 PNG 会落到 `sprites_dir/<name>/Fish-<N>.png`。
        """
        self._sprites_dir = sprites_dir
        # 未完成帧表：key 是 (sprite_name, frame_index) 元组，value 见类注释。
        self._pending = {}

    # ── feed a chunk ──────────────────────────────────────────

    def feed_chunk(self, info):
        """
        处理一个 SPRITE_CHUNK 消息字典（由 message.unpack_sprite_chunk 解出）。

        返回：
        - True  ：本帧已收齐，已落盘；调用方应触发 SpriteManager rescan
        - False ：仍在收集中，或本帧已因缺 chunk 失败被丢弃

        关键步骤：
        1) 查 _pending；不存在则建新 entry（先按需淘汰旧条目）
        2) 写入当前 chunk（重复则覆盖，幂等）
        3) 位掩码比较判定完整；完整则按 idx 排序拼接、写盘、清理 entry
        """
        key = (info["name"], info["frame_index"])
        entry = self._pending.get(key)

        # ── 新建 entry（必要时淘汰最早一条）──
        if entry is None:
            if len(self._pending) >= self.MAX_PENDING:
                self._drop_oldest()
            entry = {
                "total": info["total_chunks"],
                "received": 0,        # 32-bit 位掩码，每位对应一个 chunk idx
                "chunks": {},
            }
            self._pending[key] = entry

        # ── 写入 chunk（重复时用新数据覆盖，等价于幂等）──
        ci = info["chunk_index"]
        if ci not in entry["chunks"]:
            entry["chunks"][ci] = info["data"]
            # 把第 ci 位置 1；用 OR 避免重复设置产生副作用
            entry["received"] |= (1 << ci)

        # ── 完整性判定：前 total 位是否全部 1 ──
        if entry["total"] == 0:
            return False
        # (1 << total) - 1 即低 total 位全 1 的掩码
        expected_mask = (1 << entry["total"]) - 1
        if (entry["received"] & expected_mask) != expected_mask:
            return False

        # ── 完整：按 idx 顺序拼接，落盘 ──
        ordered = []
        for i in range(entry["total"]):
            if i in entry["chunks"]:
                ordered.append(entry["chunks"][i])
            else:
                # 理论上被完整性判定挡住；这里再保险一次
                del self._pending[key]
                return False

        data = b"".join(ordered)
        self._save_frame(info["name"], info["frame_index"], data)
        del self._pending[key]
        return True

    def _save_frame(self, name, frame_index, data):
        """
        把重组后的 PNG 字节流写入
            <sprites_dir>/<name>/Fish-(frame_index+1).png

        注意：frame_index 是 0 基，但文件名是 1 基（Fish-1.png），故 +1。
        """
        dest_dir = os.path.join(self._sprites_dir, name)
        os.makedirs(dest_dir, exist_ok=True)
        # frame_index + 1：约定 0 基 → 1 基文件名
        filename = f"Fish-{frame_index + 1}.png"
        dest = os.path.join(dest_dir, filename)
        with open(dest, "wb") as f:
            f.write(data)
        print(f"[SpriteSync] saved {filename} to {name}/")

    def _drop_oldest(self):
        """
        淘汰最早插入的 pending 条目以腾出名额。
        Python 3.7+ dict 保持插入序，所以 next(iter(...)) 必然是"最老"。
        """
        if self._pending:
            oldest = next(iter(self._pending))
            del self._pending[oldest]

    def pending_count(self):
        """当前未完成帧数（监控/调试用）。"""
        return len(self._pending)
