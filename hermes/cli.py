# -*- coding: utf-8 -*-
"""Hermes WeChat 命令行入口

用法:
  python -m hermes doctor                          # 环境自检 (数据目录/密钥/LLM/推送)
  python -m hermes groups                          # 列出可搜索的群/会话
  python -m hermes daily [days] [群关键词...]       # 群知识日报
  python -m hermes mp [days]                       # 公众号文章日报
"""
import sys

from . import config, collector


def _print_env():
    print("HERMES_DB_DIR     =", config.DB_DIR or "(未设置, 将自动检测)")
    print("HERMES_KEYS_FILE  =", config.KEYS_FILE or "(默认 ~/.wechat-cli/all_keys.json)")
    print("HERMES_WORK_DIR   =", config.WORK_DIR)
    print("LLM_BASE_URL      =", config.LLM_BASE_URL)
    print("LLM_MODEL         =", config.LLM_MODEL)
    print("LLM_API_KEY       =", "已设置" if config.LLM_API_KEY else "(未设置)")
    print("LLM_PROXY         =", config.LLM_PROXY or "(直连)")
    print("Discord 推送      =", "已配置" if config.discord_ready() else "(未配置, 仅本地输出)")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "doctor"

    if cmd == "doctor":
        _print_env()
        print()
        try:
            db = config.resolve_db_dir()
            print("[OK] 微信数据目录:", db)
        except Exception as e:
            print("[!!]", e)
            return 1
        kf = config.resolve_keys_file()
        if config.KEYS_FILE and config.KEYS_FILE != kf:
            pass
        import os
        if os.path.exists(kf):
            n = len(__import__("json").load(open(kf, encoding="utf-8")))
            print("[OK] 密钥文件: {} ({} 个库)".format(kf, n))
        else:
            print("[!!] 密钥文件不存在: {} — 先运行 wechat-cli init".format(kf))
            return 1
        print("[OK] LLM: {} ({}) {}".format(
            config.LLM_MODEL, config.LLM_BASE_URL,
            "key已配置" if config.LLM_API_KEY else "缺 LLM_API_KEY"))
        return 0

    if cmd == "groups":
        collector.ensure_core_dbs()
        kw = argv[1] if len(argv) > 1 else ""
        for r in collector.find_chat(kw) if kw else []:
            print(r)
        if not kw:
            import sqlite3, os
            con = sqlite3.connect(os.path.join(config.DEC_DIR, "contact_contact.db"))
            rows = con.execute(
                "SELECT nick_name FROM contact WHERE is_in_chat_room=1 "
                "AND nick_name != '' ORDER BY nick_name").fetchall()
            con.close()
            for (n,) in rows:
                print(n)
        return 0

    if cmd == "daily":
        from . import daily
        days = int(argv[1]) if len(argv) > 1 else 1
        groups = argv[2:] or ["Agentic", "Data Go"]
        daily.run_groups(groups, days)
        return 0

    if cmd == "mp":
        from . import daily
        days = int(argv[1]) if len(argv) > 1 else 3
        daily.run_mp(days)
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
