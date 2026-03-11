#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import json
import os
import subprocess
import time
from typing import Any, Dict, List


def split_into_batches(data: List[Dict[str, Any]], batch_size: int):
    """将大列表拆分成多个小批次"""
    for i in range(0, len(data), batch_size):
        yield data[i : i + batch_size]


def upload_batch(
    *,
    cmc_path: str,
    contract_name: str,
    method: str,
    sdk_conf: str,
    batch_data: List[Dict[str, Any]],
    batch_index: int,
    sync_result: bool,
):
    """上传单个批次，返回 (ok, stdout, stderr)"""
    batch_str = json.dumps(batch_data, ensure_ascii=False)

    # 注意：--params 需要传 JSON 对象；其中 batch_logs 的值是一个“字符串”，其内容是 JSON 数组
    params_obj = {"batch_logs": batch_str}
    params_str = json.dumps(params_obj, ensure_ascii=False)

    cmd = [
        cmc_path,
        "client",
        "contract",
        "user",
        "invoke",
        "--contract-name",
        contract_name,
        "--method",
        method,
        "--sdk-conf-path",
        sdk_conf,
        "--params",
        params_str,
        "--sync-result",
        "true" if sync_result else "false",
    ]

    print(f"[批次 {batch_index}] 正在上传 {len(batch_data)} 条日志...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    ok = (result.returncode == 0) and ("SUCCESS" in (result.stdout or ""))
    if ok:
        print(f"[批次 {batch_index}] 上传成功")
    else:
        print(f"[批次 {batch_index}] 上传失败（returncode={result.returncode}）")

    return ok, (result.stdout or ""), (result.stderr or "")


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))

    parser = argparse.ArgumentParser(description="使用 cmc 批量调用合约 AddBatchLog 上链 evidence_full_data.json")
    parser.add_argument("--contract-name", default="aegis_sense_log", help="合约名")
    parser.add_argument("--method", default="AddBatchLog", help="合约方法名")
    parser.add_argument("--cmc-path", default=os.path.join(here, "cmc"), help="cmc 可执行文件路径")
    parser.add_argument("--sdk-conf", default=os.path.join(here, "testdata", "sdk_config.yml"), help="sdk_config.yml 路径")
    parser.add_argument(
        "--input-file",
        default=os.path.join(repo_root, "HashCaculating", "output", "evidence_full_data.json"),
        help="原始数据文件（JSON 数组）路径",
    )
    parser.add_argument("--batch-size", type=int, default=2000, help="每批最大条数（必须 ≤ 合约 MaxBatchSize）")
    parser.add_argument("--sleep", type=float, default=0.5, help="每批上传后的延时（秒）")
    parser.add_argument("--sync-result", action="store_true", default=True, help="是否同步等待交易结果（默认 true）")
    parser.add_argument("--start-batch", type=int, default=1, help="从第几批开始（用于断点续传）")
    args = parser.parse_args()

    if not os.path.exists(args.cmc_path):
        print(f"错误：cmc 不存在：{args.cmc_path}")
        return 2
    if not os.path.exists(args.sdk_conf):
        print(f"错误：sdk_config.yml 不存在：{args.sdk_conf}")
        return 2
    if not os.path.exists(args.input_file):
        print(f"错误：文件不存在：{args.input_file}")
        return 2
    if args.batch_size <= 0:
        print("错误：batch-size 必须 > 0")
        return 2

    with open(args.input_file, "r", encoding="utf-8") as f:
        all_data = json.load(f)
    if not isinstance(all_data, list):
        print("错误：输入文件必须是 JSON 数组（list）")
        return 2

    total = len(all_data)
    print(f"共读取 {total} 条日志数据：{args.input_file}")
    print(f"批大小：{args.batch_size}，合约：{args.contract_name}，方法：{args.method}")

    success_count = 0
    batches = list(split_into_batches(all_data, args.batch_size))
    total_batches = len(batches)
    print(f"总批次数：{total_batches}")

    for idx, batch in enumerate(batches, start=1):
        if idx < args.start_batch:
            continue

        ok, out, err = upload_batch(
            cmc_path=args.cmc_path,
            contract_name=args.contract_name,
            method=args.method,
            sdk_conf=args.sdk_conf,
            batch_data=batch,
            batch_index=idx,
            sync_result=args.sync_result,
        )

        if ok:
            success_count += len(batch)
        else:
            print("stdout：")
            print(out)
            print("stderr：")
            print(err)
            failed_path = os.path.join(here, f"failed_batch_{idx}.json")
            with open(failed_path, "w", encoding="utf-8") as ff:
                json.dump(batch, ff, ensure_ascii=False, indent=2)
            print(f"已将失败批次保存到：{failed_path}")
            print(f"停止后续上传。你可以用 --start-batch {idx} 结合修复后重试。")
            break

        if args.sleep > 0:
            time.sleep(args.sleep)

    print("\n=== 上传完成 ===")
    print(f"成功上传：{success_count} 条")
    if success_count < total:
        print(f"未上传：{total - success_count} 条（请检查失败批次与错误日志）")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

