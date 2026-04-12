#!/usr/bin/env python3
"""
生成前端所需的所有数据。
"""
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from src.dashboard_builder import DashboardDataBuilder


OUTPUT_DIR = root_dir / "web" / "public"


def main():
    print("=" * 60)
    print("生成前端数据")
    print("=" * 60)

    builder = DashboardDataBuilder(root_dir)
    try:
        data_path, ranking_path = builder.write_outputs(OUTPUT_DIR)
        print(f"\n数据已保存：{data_path}")
        print(f"排名已保存：{ranking_path}")
    finally:
        builder.close()


if __name__ == "__main__":
    main()
