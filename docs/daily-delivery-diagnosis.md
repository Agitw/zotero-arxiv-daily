# 每日推送失败诊断

检查日期：2026-09-27。工作流：`Send emails daily`（`.github/workflows/main.yml`）。

## 结论

已核实的失败发生在论文检索阶段。最近 20 次每日运行中有 8 次失败、12 次成功，9 月 23–27 日连续 5 次失败。两个外部论文源的异常会直接终止整个流程，使后续来源和邮件发送无法执行。

### 运行证据

日期按 GitHub 日志的 UTC 日期列出，当前列出的运行在上海时间也是同一天。

| 日期 | 结果 | 异常 | 运行链接 |
| --- | --- | --- | --- |
| 2026-09-27 | 失败 | bioRxiv `requests.exceptions.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` | [36282268047](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/36282268047) |
| 2026-09-26 | 失败 | arXiv API HTTP 406 | [36204871104](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/36204871104) |
| 2026-09-25 | 失败 | arXiv API HTTP 406 | [36077166341](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/36077166341) |
| 2026-09-24 | 失败 | arXiv API HTTP 406 | [35937850097](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/35937850097) |
| 2026-09-23 | 失败 | arXiv API HTTP 406，245 个候选中完成 20 个后退出 | [35800830968](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/35800830968) |
| 2026-09-22 | 成功 | 同一提交可完成邮件发送和历史保存 | [35672856706](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/35672856706) |
| 2026-09-17 | 失败 | bioRxiv JSON 解析失败 | [35165668782](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/35165668782) |
| 2026-09-15 | 失败 | arXiv API HTTP 503 | [34913032767](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/34913032767) |
| 2026-09-11 | 失败 | arXiv API HTTP 503 | [34660052511](https://github.com/Agitw/zotero-arxiv-daily/actions/runs/34660052511) |

最近检查到的这些运行使用提交 `ea671150ca358eff9d4568182639115ddb2dd3b1`。

## 已确认的代码问题

1. `BiorxivRetriever._retrieve_raw_papers()` 原先只重试请求和 HTTP 状态检查，`response.json()` 位于循环之外。即使 HTTP 200，只要正文为空或不是 JSON，就立刻退出，完全没有重试机会。请求也没有超时设置。medRxiv 继承相同实现。
2. `ArxivRetriever._retrieve_raw_papers()` 先读 Atom feed 获取论文 ID，再向 `export.arxiv.org` 查询完整元数据。API 406/503 等异常重试后仍向上抛出；已获取的 RSS 摘要未用于恢复，前面成功的批次也无法进入后续处理。
3. `Executor._run_pipeline()` 对来源逐一调用但没有检索异常边界。一个来源失败即中断后续来源、排序、摘要和邮件发送。

GitHub 日志没有保留 406 的响应正文，无法由现有证据进一步确定服务端拒绝请求的具体原因。JSON 错误只能证明响应不能解析为 JSON，不能据此断言正文一定是 HTML 或为空。

## 本地修复

- bioRxiv / medRxiv：请求使用 `(10, 60)` 秒连接/读取超时；请求、JSON 解析和 collection 结构检查均纳入最多 3 次重试，重试间隔为 10 / 20 秒。失败后抛出明确的 `SourceRetrievalError`。
- arXiv：避免叠加多层重试。API 在有限重试后仍返回 406、429、500、502、503、504，或连接/分页异常时，改用已有 Atom feed 元数据；本次运行剩余批次不再反复请求失效 API，前面已成功的批次保留。
- 来源隔离：请求异常与 `SourceRetrievalError` 记录后跳过该来源，继续其它来源。TypeError 等程序错误仍抛出。全部来源抛出检索异常时仍标记整次运行失败。
- 诊断报告：`outputs/recommendation-funnel.json` 新增 `sources`，记录每个来源的 `success` / `degraded` / `failed`、论文数、降级原因和错误。

RSS 回退采用官方 feed 中的标题、摘要、作者及公告日期，并继续使用既有日期过滤。回退论文没有下载全文，因此可能缺少从全文提取的机构信息。字段含义参见 [arXiv 官方 Atom 规范](https://info.arxiv.org/help/atom_specifications.html)。

## 验证

新增 `tests/test_retrieval_resilience.py`。在修复前重放线上异常：**5 failed**；应用修复后同一组用例：**5 passed**。

补充边界用例后，与已有检索、Executor 和 funnel 测试共同验证：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& '.\.venv\Scripts\python.exe' -m pytest tests/test_retrieval_resilience.py tests/retriever tests/test_executor.py tests/test_recommendation_funnel.py -q --tb=short
```

结果：**64 passed in 22.78s**。测试中的外部来源、LLM 和邮件发送使用离线替身，没有发送真实邮件。

环境先使用指定的 codex conda（Python 3.11.15）。该环境首次扩展验证得到 61 passed / 3 failed；失败全部来自原有 `glob.translate()` 对 Python 3.13 的依赖，项目也明确声明 `requires-python >=3.13`。确认版本冲突后，按环境规则例外改用项目已有 `.venv`（Python 3.13.14）进行最终验证。缺失依赖只安装进 codex，未创建新环境。

## 部署状态

用户已要求将新版本提交并推送到 GitHub `main`，与此前的工作日日期窗口提交一并发布。本次没有手动触发真实发送工作流。发布后的每日任务需核对 `Run script` 日志及 funnel artifact：外部来源仍异常时，应出现 RSS 降级或来源跳过记录，并让其它有效候选继续到邮件发送。
