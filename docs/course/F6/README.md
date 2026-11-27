# CoreOrder 课程答辩交付

[团队 PPTX](CoreOrder-Defense.pptx) · [团队 PDF](CoreOrder-Defense.pdf) · [五人附页 PPTX](CoreOrder-Contributions.pptx) · [五人附页 PDF](CoreOrder-Contributions.pdf) · [五人讲稿和 42 问 Word](CoreOrder-Defense-Scripts.docx)

19 页团队课件讲述轨迹保持、PAMS、增量堆、原生路径、多核和真实任务粒度、AoS/SoA 与 Cache、完整系统收益和瓶颈迁移。10 页个人附页按 A–E 分组，每人两页，分别陈述原始实现和实证。建议排练时间约 12 分钟，实际答辩安排按课程通知。

- [Markdown 逐人讲稿与问答](DEFENSE.md) · [提交与贡献映射](CONTRIBUTIONS.md)
- [实跑和离线 Demo](DEMO.md) · [人员复现任务单](REPRODUCTION.md)
- [课件验证](QA.md) · [最终审计](../../gates/FINAL.md)

可编辑课件使用 [生成脚本](build-slides.cjs) 和 PptxGenJS。重新导出需让 LibreOffice 可见 Noto Sans CJK SC Regular/Bold，同时为中文 PDF 检查字形嵌入。

```bash
node docs/course/F6/build-slides.cjs
soffice --headless --convert-to pdf --outdir docs/course/F6 \
  docs/course/F6/CoreOrder-Defense.pptx docs/course/F6/CoreOrder-Contributions.pptx
pandoc docs/course/F6/DEFENSE.md -f gfm -o docs/course/F6/CoreOrder-Defense-Scripts.docx
(cd docs/course/F6 && shasum -a 256 -c SHA256SUMS)
```
