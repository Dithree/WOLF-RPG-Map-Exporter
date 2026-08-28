# -*- coding: utf-8 -*-
"""Spawn the editor suspended, hook before startup, resume, capture auto-open render.

Usage:
    python export_spawn.py [out.png]
"""
import os
import sys
import time

import frida

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import wolfrpg_export as we

# Point at the Desktop editor (avoids Chinese-path env issues)
_DESKTOP_EDITOR = r'D:\文档转移\Desktop\WOLF地图导出工具_1.4\WOLF_RPG_Editor3'
if os.path.isdir(_DESKTOP_EDITOR):
    we.EDITOR_DIR = _DESKTOP_EDITOR
    we.EDITOR_EXE = os.path.join(_DESKTOP_EDITOR, 'Editor.exe')


def main():
    out_png = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.join(we.OUT_DIR, 'spawn_capture.png')

    # kill existing editor
    import subprocess
    subprocess.run(['powershell', '-Command',
                    'Get-Process -Name Editor -ErrorAction SilentlyContinue | Stop-Process -Force'],
                   capture_output=True)
    time.sleep(1)

    device = frida.get_local_device()
    pid = device.spawn([we.EDITOR_EXE], cwd=we.EDITOR_DIR)
    print('spawned pid', pid, file=sys.stderr)

    session = device.attach(pid)
    script = session.create_script(we.JS)
    state = {'records': [], 'bitmaps': {}, 'collecting': True, 'last_tile_t': time.time()}

    def on_message(msg, data):
        if msg['type'] == 'send':
            p = msg['payload']
            if isinstance(p, dict) and p.get('type') == 'bmp':
                state['bitmaps'][p['hbmp']] = (p['w'], p['h'], bytes(data) if data else b'')
            else:
                if state['collecting']:
                    state['records'].append(p)
                    if p.get('n') == 'AlphaBlend' and p.get('wDest') in (16, 32) and p.get('hDest') in (16, 32):
                        state['last_tile_t'] = time.time()
        elif msg['type'] == 'error':
            print('JS ERROR:', msg.get('stack') or msg.get('description'), file=sys.stderr)

    script.on('message', on_message)
    script.load()
    print('hooks loaded before resume', file=sys.stderr)

    device.resume(pid)
    print('resumed, waiting for render...', file=sys.stderr)

    start = time.time()
    while time.time() - start < 20:
        tiles = len([r for r in state['records'] if r.get('n') == 'AlphaBlend' and r.get('wDest') in (16, 32) and r.get('hDest') in (16, 32)])
        if tiles > 0 and (time.time() - state['last_tile_t']) > 0.8:
            break
        time.sleep(0.05)
    time.sleep(0.5)
    state['collecting'] = False

    records = state['records']
    cur_file = we.get_current_map_file()
    map_path = os.path.join(we.EDITOR_DIR, 'Data', 'MapData', cur_file) if cur_file else None
    if map_path is None or not os.path.exists(map_path):
        print(f'cannot locate current map (title={we.get_editor_title()!r})', file=sys.stderr)
        map_path = None

    cnt = we.replay_export(cur_file or 'spawn', records, state['bitmaps'], out_png, map_path, kind='map')
    print(f'tiles {cnt} -> {out_png}', file=sys.stderr)

    session.detach()
    try:
        device.kill(pid)
    except Exception:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
