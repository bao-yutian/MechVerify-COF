# COF Mechanosynthesis AI Auditor｜第一版进度

## 为什么要做

AI 能读懂论文中的词句，但可能把“球磨加速反应”误判成“球磨提高结晶度”，或者把某个频率范围内的实验结果推广到未测试的条件。我们要开发一个能核对实验条件和证据的科学 AI 审核器。

## 已经有的 Output

1. **代码**：`mechverify/`，结构化证据检查器、可选 LLM 接口、评价指标。
2. **数据**：`data/pilot_cases_for_review.csv` 有 15 道来自三篇论文的试点题；`evidence.json` 有 11 条带出处的实验事实。
3. **报告**：`results/always_supported.json` 与 `results/structured_sanity.json`，演示指标计算（尚无实际 LLM 对比实验）。
4. **测试**：7 项自动化测试，可重复运行。

注意：第三篇的证据仅核对过**出版社摘要**，后续需要查全文及补充材料；其他数据虽已查正文，也尚未经过独立第二人标注。

## 如何在电脑上运行

安装 Python 3.10 或更高版本，把本文件夹解压，进入该目录，在终端运行：

```bash
python -m mechverify inspect
python -m mechverify check H-04
python -m mechverify evaluate --strategy structured
python -m unittest discover -s tests -v
```

前两行会打印 15 道题及 H-04 的审核过程。`structured` 模式使用**人工预先整理的结构化数据**，目的是检查程序逻辑；不能代表 LLM 的真实性能。

可选：按 `README.md` 设置自己的 LLM API 信息后执行 `python -m mechverify evaluate --strategy llm`，程序会把 Claim 和证据文本交给 LLM 评分。

## 如何放到 GitHub

在 GitHub 网页新建一个空仓库，例如 `mechverify-cof`。在本文件夹的终端运行（替换你的用户名）：

```bash
git init
git add .
git commit -m "Initial COF mechanosynthesis verification pilot"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/mechverify-cof.git
git push -u origin main
```

不要上传 API 密钥、未发表的科研资料或无版权许可的论文全文。

## 下一步最优先的两件事

1. 对照原论文与 SI 独立复核 15 道题，尤其是 2026 年 ACS 论文，补全 `reviewer_notes`。
2. 运行一个真实 LLM baseline，记录模型原始回答，找出哪些题 LLM 真会判断错误。只有证明了明确错误类型，我们才需要加入更复杂的 Physics Checker 或 RAG。