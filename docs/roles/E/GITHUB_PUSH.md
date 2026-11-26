# 成员 E 的 GitHub 推送步骤

此目录是GitHub轻量交付工作树，分支为 `e/03-github-delivery`。原 `CoreOrder` 目录及 `e/01-protocol`、`e/02-oracle`、`e/03-system-check` 分支完整保留。
之前的完整交付包适合离线移交。本分支按团队GitHub手册第4、8节，把大型原始轨迹/profile/完整反例移至已有归档，避免进入普通代码PR的提交历史。源码、测试和实验模板逐文件保持与原交付相同。

## 推送的内容

`validation/`、`experiments/`、`tests/differential/`、`configs/experiments/`、E所属的 `docs/`；`results/` 保留真实命令/环境/状态/比较元数据、日志、代表fixture及反例索引。
完整原始证据与原阶段提交历史通过 `CoreOrder_E1-E3.bundle` 单独交给组长；校验值及每个归档文件索引见 `EVIDENCE_ARCHIVE.json`。原始结果没有改写或删除。

## 操作

组长在仓库中邀请本人GitHub账号为Collaborator，本人接受邀请。提交姓名和邮箱只是Git署名，不代替仓库访问授权。

在PowerShell执行：

```powershell
cd "C:\Users\Lenovo\Desktop\计组作业\CoreOrder_Member_E\CoreOrder_GitHub"
git status --short --branch
git branch --show-current
git push -u origin e/03-github-delivery
```

确认显示的分支为 `e/03-github-delivery`，工作树干净。当前代码已在本地提交，不需要再运行git add或git commit。
推送时使用本人的GitHub登录凭据。出现403或Permission denied时，先检查是否接受了正确账号的仓库邀请，再重试同一push命令。

成功后打开仓库分支页面，把分支链接和 `git rev-parse HEAD` 输出发给组长，由组长安排review/PR/合并。
只推送上面明确指定的E分支；无需推送main、所有本地分支或任何归档ZIP。

状态描述：E1–E3可独立完成部分MODULE_PASS，生产系统G0/G1/G2仍INTEGRATION_PENDING，正式性能NOT_RUN。该push不会让待集成项变成通过。

来源：[GitHub push文档](https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository)、[邀请协作者](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/repository-access-and-collaboration/inviting-collaborators-to-a-personal-repository)。
