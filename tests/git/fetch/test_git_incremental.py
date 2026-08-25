"""
通过 Git Protocol (git://) 学习增量拉取流程

流程:
1. Discovery: 获取 git://git.lyoko.io/AzurLaneAutoScript 的引用
2. Base: 下载 v0.5.1
3. Increment: 在已知 v0.5.1 的基础上，下载 v0.5.2 的变更
"""
import os

import trio

from alasio.git.fetch.argument import Arguments
from alasio.git.fetch.pkt import FetchPayload
from alasio.git.fetch.transport_git import GitTransport


async def main():
    repo_url = "git://git.lyoko.io/AzurLaneAutoScript"
    repo_path = r'c:\Users\s-desktop\docker\alasio'

    args = Arguments(repo_path=repo_path, repo_url=repo_url)
    transport = GitTransport(args)

    print(f"🌐 目标: {repo_url}")

    # 步骤 1: 获取所有引用 (ls-remote 模拟)
    print("\n[Step 1] 获取引用列表...")
    refs = await transport.fetch_refs()

    v051_sha = refs[b'refs/tags/v0.5.1'].decode() if b'refs/tags/v0.5.1' in refs else "50f49a6350aa584d96dc4efe162cec8ce09a212b"
    v052_sha = refs[b'refs/tags/v0.5.2'].decode() if b'refs/tags/v0.5.2' in refs else "8b955975df6f7af8b8411f9b753ff84c26adf110"

    print(f"📍 v0.5.1 SHA: {v051_sha}")
    print(f"📍 v0.5.2 SHA: {v052_sha}")

    # 步骤 2: 初始拉取 v0.5.1
    print("\n[Step 2] 模拟初始拉取 (v0.5.1)...")
    payload1 = FetchPayload()
    # 注意: transport_git 目前主要支持 v1 逻辑
    payload1.add_line(f"want {v051_sha} {transport.capabilities.as_string()}")
    payload1.add_delimiter()
    payload1.add_done()

    pack1 = os.path.join(repo_path, "local_v051.pack")
    await transport.fetch_pack_v1(payload1, output_file=pack1)
    size1 = os.path.getsize(pack1)
    print(f"✅ 下载完成, 大小: {size1 / 1024:.2f} KB")

    # 步骤 3: 增量拉取 v0.5.2
    # 这是最关键的学习点：我们告诉服务器我们要 v0.5.2，但我们已经有 (have) v0.5.1 了
    print("\n[Step 3] 模拟增量拉取 (请求 v0.5.2，告知已有 v0.5.1)...")
    payload2 = FetchPayload()

    # 想要新的
    payload2.add_line(f"want {v052_sha} {transport.capabilities.as_string()}")
    payload2.add_delimiter()

    # 告知旧的 (Negotiation 核心)
    print(f"🤝 协商: have {v051_sha}")
    payload2.add_have(v051_sha)
    payload2.add_done()

    pack2 = os.path.join(repo_path, "local_update_v052.pack")

    # 调用 v1 或 v2 都可以，为了兼容性这里使用 v1 逻辑
    await transport.fetch_pack_v1(payload2, output_file=pack2)
    size2 = os.path.getsize(pack2)
    print(f"✅ 增量包下载完成, 大小: {size2 / 1024:.2f} KB")

    print("\n" + "=" * 40)
    print(f"📊 流量对比:")
    print(f"   完整 v0.5.1: {size1 / 1024:.2f} KB")
    print(f"   增量 v0.5.2: {size2 / 1024:.2f} KB")
    print(f"   节省了约 { (1 - size2 / size1) * 100:.1f}% 的流量")
    print("=" * 40)


if __name__ == "__main__":
    trio.run(main)
