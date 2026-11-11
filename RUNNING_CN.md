# 如何运行 MechVerify-COF（中文）

本仓库有两种运行模式：**不需要 GPU 的证据/规则测试**，以及**需要模型运行环境的 LLM 基线**。不要把规则测试的准确率当成 AI 准确率。

## A. 最简单：GitHub Actions 自动运行（不需要安装 Python）

1. 打开仓库的 **Actions** 标签。
2. 找到 **COF Pilot Checks**。
3. 点 **Run workflow**，选择 `main`，再点绿色的 **Run workflow**。第一次使用时 GitHub 可能要求启用 Actions。
4. 等待运行结束，打开该运行查看 **Run unit tests**、**Run non-LLM baseline** 和 **Run structured sanity check** 的日志。
5. 在运行页面的 **Artifacts** 下载 `cof-cpu-pilot-reports`（JSON 报告）。

推送 `main` 或提交 PR 也会触发该流程。此流程**不会下载或运行 Qwen**，只运行 CPU 上的 Python 单元测试与两种不依赖 API 的 baseline。它也**不会**将生成的运行结果自动提交回仓库。

## B. Google Colab（同样可运行 CPU 测试）

新建 Colab Notebook，运行：

```python
!git clone https://github.com/bao-yutian/MechVerify-COF.git
%cd MechVerify-COF
!python -m unittest discover -s tests -v
!python -m mechverify inspect
!python -m mechverify evaluate --strategy structured
```

如果再次执行 `git clone` 报文件夹已存在，重启运行时或先删除之前 clone 的目录。私有仓库需要额外授权，切勿在公开 Notebook 中粘贴个人访问令牌。

## C. 在自己的计算机上运行

```bash
git clone https://github.com/bao-yutian/MechVerify-COF.git
cd MechVerify-COF
python -m unittest discover -s tests -v
python -m mechverify evaluate --strategy always-supported
python -m mechverify evaluate --strategy structured
```

要求 Python 3.10 或以上。首版标准库代码无需 pip 安装。

## D. 真正的 Qwen 评估

当前仓库的 `--strategy llm` 使用外部 **OpenAI-compatible API**，需要用户自己提供 endpoint、模型名和密钥，**不是**此前 Colab 里下载的本地 Qwen。两条运行路径不能直接混用。

没有 API key 时，推荐下一步在 Colab GPU 上加入**本地 Qwen 基线**的脚本或 notebook，读取 `data/cases.json` 和 `data/evidence.json`，输出同一套 SUPPORTED / CONTRADICTED / INSUFFICIENT 标签，再使用 `mechverify/evaluation.py` 计算指标。Colab GPU 免费额度及可用性不保证。

## 科学注意事项

- 15 道试点题来自三篇论文；其中 U 论文目前仅核对了摘要。
- `structured` 检查器读取人工已结构化好的 Claim，展示的是数据/规则逻辑是否一致，**不是 AI 能力或泛化性能**。
- 不要在 GitHub 上传未发表 DFT 数据、私有 PDF、API 密钥或其他敏感数据。
