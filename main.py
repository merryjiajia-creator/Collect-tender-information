#!/usr/bin/env python3
"""招标信息监控 —— 程序入口。

用法：
    python main.py            # 执行一次完整任务（搜索→解析→写表→看板→企微推送）
    python main.py --dry-run  # 仅本地跑通（不写在线表格、不推送），用于调试

四类主题：物码 / 即时零售 / 到店 / AI
"""
import argparse
import logging
import sys

from tender_monitor.pipeline import run
from tender_monitor.config import config


def main():
    parser = argparse.ArgumentParser(description="招标信息监控自动化任务")
    parser.add_argument("--dry-run", action="store_true",
                        help="仅本地执行，不写在线表格、不推送企微")
    args = parser.parse_args()

    if args.dry_run:
        # 通过临时清空关键配置实现 dry-run
        config.TENCENT_CLIENT_ID = ""
        config.WECOM_WEBHOOK_URL = ""
        logging.info("DRY-RUN 模式：跳过在线表格写入与企微推送")

    try:
        result = run()
        print(f"完成：新增 {result['new']} 条，累计 {result['total']} 条")
    except Exception as e:
        logging.exception("任务执行失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
