// Run from the repository root: node docs/course/F6/build-slides.cjs
const fs = require("node:fs");
const path = require("node:path");
const pptxgen = require("pptxgenjs");

const here = __dirname;
const repo = path.resolve(here, "../../..");
const evidence = path.join(repo, "docs/gates/evidence");
const read = (relative) => JSON.parse(fs.readFileSync(path.join(evidence, relative), "utf8"));
const demo = read("F6/demo-receipt.json");
const granularity = read("T05/analysis.json");
const results = JSON.parse(fs.readFileSync(path.join(repo,"docs/results/results.json"),"utf8"));
function effect(group, reference, variant, endpoint="simulation_s") {
  return results.timing[[group,reference,variant].join("|")][endpoint];
}
function interval(record) { return record.point+"× ["+record.low+", "+record.high+"]"; }
const system = "E01-W2-H-system";
const colors = { ink: "152B40", teal: "08766E", quiet: "4F6473", faint: "DCE6EB", paper: "FFFFFF", shade: "F1F7F7" };
const font = "Noto Sans CJK SC";
const w = 13.3333;
const x = .82;
const contentY = 2.12;

function deck(title) {
  const ppt = new pptxgen();
  ppt.layout = "LAYOUT_WIDE";
  ppt.author = "Parallel";
  ppt.subject = "计算机组成原理课程项目答辩";
  ppt.title = title;
  ppt.lang = "zh-CN";
  ppt.theme = { headFontFace: font, bodyFontFace: font, lang: "zh-CN" };
  return ppt;
}

function text(slide, value, xx, yy, ww, hh, options = {}) {
  slide.addText(value, {
    x: xx, y: yy, w: ww, h: hh, fontFace: font, lang: "zh-CN", fontSize: 22,
    color: colors.ink, margin: 0, valign: "mid", breakLine: false, ...options,
  });
}

function rule(slide, xx, yy, ww, color = colors.faint) {
  slide.addShape("line", { x: xx, y: yy, w: ww, h: 0, line: { color, width: .8 } });
}

function shell(ppt, {section, title, source, notes}) {
  const slide = ppt.addSlide();
  slide.background = { color: colors.paper };
  text(slide, section, x, .54, 10.8, .30, { fontSize: 15, color: colors.teal, bold: true });
  text(slide, title, x, .98, 11.65, .77, { fontSize: 32, bold: true });
  rule(slide, x, 6.84, w - 2 * x);
  text(slide, source, x, 6.96, 11.1, .24, { fontSize: 11, color: colors.quiet });
  text(slide, String(ppt._slides.length).padStart(2, "0"), 12.0, 6.93, .5, .3, { fontSize: 12, color: colors.quiet, align: "right" });
  slide.addNotes(notes);
  return slide;
}

function rows(slide, data, widths, {atX = x, atY = contentY, height = .60, fontSize = 20, head = true} = {}) {
  const total = widths.reduce((a,b)=>a+b, 0);
  data.forEach((row, i) => {
    const y = atY + height * i;
    if (i === 0 && head) {
      slide.addShape("rect", { x: atX, y, w: total, h: height, fill: {color: colors.shade}, line: {transparency: 100} });
    }
    rule(slide, atX, y + height, total);
    let xx = atX;
    row.forEach((value, j) => {
      text(slide, String(value), xx + .11, y + .04, widths[j] - .22, height - .08,
        { fontSize, bold: (i === 0 && head) || j === 0, color: i === 0 && head ? colors.teal : colors.ink });
      xx += widths[j];
    });
  });
}
function callout(slide, value, yy = 5.94, options = {}) {
  text(slide, value, x, yy, 11.64, .58, { fontSize: 21, bold: true, color: colors.teal, ...options });
}
function aside(slide, title, lines) {
  text(slide, title, 8.39, 2.40, 4.09, .73, { color: colors.teal, fontSize: 29, bold: true });
  lines.forEach((line, i) => text(slide, line, 8.40, 3.36 + .70*i, 4.05, .55, {fontSize: 19}));
}
function chart(slide, type, series, opts) {
  slide.addChart(type, series, {
    x, y: contentY, w: 7.18, h: 3.90,
    chartColors: [colors.teal, "476C91", "AD6839", "889AA6"],
    showTitle: false, showLegend: true, legendPos: "b", legendFontFace: font, legendFontSize: 12,
    catAxisLabelFontFace: font, catAxisLabelFontSize: 12, catAxisLabelColor: colors.quiet,
    valAxisLabelFontFace: font, valAxisLabelFontSize: 12, valAxisLabelColor: colors.quiet,
    valGridLine: { color: colors.faint, size: .75 }, showCatName: false,
    showMarker: true, markerSize: 6, lineSize: 2.2,
    ...opts,
  });
}
function flow(slide, labels, yy) {
  const widths = (11.66 - .35 * (labels.length - 1)) / labels.length;
  labels.forEach((label, i) => {
    const xx = x + i * (widths + .35);
    slide.addShape("rect", { x: xx, y: yy, w: widths, h: .79, fill: {color: colors.shade}, line: {color: colors.faint, width: .8} });
    text(slide, label, xx + .07, yy + .05, widths - .14, .69, {fontSize: 17, bold: true, align: "center"});
    if (i) slide.addShape("line", {x: xx - .31, y: yy + .39, w: .25, h: 0, line: {color: colors.teal, width: 1.25, endArrowType:"triangle"}});
  });
}
const main = deck("CoreOrder｜保持金融轨迹的 CPU 性能优化");
const cover = main.addSlide();
cover.background = {color: colors.ink};
text(cover, "计算机组成原理课程答辩", 1.00, .79, 10.8, .39, {color: "85D2C8", fontSize: 19});
text(cover, "CoreOrder", .99, 1.65, 11.2, 1.15, {color: colors.paper, fontSize: 64, bold: true});
text(cover, "保持金融轨迹的 CPU 性能优化", 1.02, 2.99, 11.1, .78, {color: colors.paper, fontSize: 33, bold: true});
text(cover, "增量堆恢复、确定性多核与内存布局", 1.04, 4.09, 10.8, .53, {color: "CDDFEA", fontSize: 21});
rule(cover, 1.04, 5.74, 11.24, "537388");
text(cover, "Parallel 团队   /   2026.11.27", 1.04, 6.04, 11.2, .38, {color: "CDDFEA", fontSize: 16});
cover.addNotes("A 开场。我们选择一套已有市场模拟器，用相同金融轨迹约束优化，考察 CPU 比较工作、任务粒度和内存层次。");

function slide(section, title, source, notes) { return shell(main, {section,title,source,notes}); }

let s = slide("研究问题", "金融轨迹给 CPU 对照实验固定了工作量", "F5 论文 §1、§3、§5",
"问清楚同一个 seed 为什么还需要核对轨迹。每次订单与成交会改变下一个时间步的市场状态、可访问行数和实际随机消耗。验证顺序和状态，让后续比较有共同分母。");
flow(s, ["随机样本和订单", "撮合与账本", "下一步市场状态", "下一批决策"], 2.55);
text(s,"在市场轨迹保持相同的条件下，恢复算法、任务粒度和数据布局怎样影响 CPU 成本？", x, 4.10, 11.6, 1.04, {fontSize: 28,bold:true});
callout(s,"比较三个层次：算法工作量、并行执行、内存访问。");

s = slide("平台与实现", "PAMS 提供市场语义和可运行的原版对照", "Hirano、Takata 与 Izumi，2023；F5 补充材料 §2",
"A 说明复用的是完整的成熟撮合、HFT、随机流和市场事件。C++ Taskflow 和 pybind11 是上游组件。CoreOrder 贡献在保序接入以及受控比较。");
rows(s,[["选择依据","实验用途"],["固定 PAMS 源码与 FCN","复用撮合、事件、账户与原版串行参考"],["同一份工作负载和 seed","对照变量可以限定为堆、后端或布局"],["固定 Taskflow 和 pybind11","使用共享 C++ 数值核和持久任务执行器"]],[4.25,7.39],{height:.72});
callout(s,"三个上游均固定到 Git 对象，回执绑定实际源码和二进制。");

s = slide("平台与实现", "安全前缀保留随机流和原始提交顺序", "F5 论文 §4.2、算法 1；src/coreorder/native_serial.py",
"A 解释剩余非空订单列表额度 r。长度不超过 r 的前缀，是原版必访问的部分。随机样本仍按智能体与市场顺序取，包含 Gaussian 缓存。遇到空结果继续收集，结果最后按原顺序进入 PAMS。");
flow(s,["按剩余名额取前缀", "依序准备 RNG", "打包并求值", "按原顺序回填"],2.45);
rows(s,[["共享观察状态","精确 FCN 类型在一轮收集里读取同一市场快照"],["空结果补批","额度按非空列表递增，光标按访问人数前进"],["顺序提交","撮合、HFT 和账户更新沿用 stock PAMS"]],[3.20,8.44],{atY:3.65,height:.58,head:false,fontSize:19});
callout(s,"并行只推进确定性数值求值，每行写独占输出。");

s = slide("增量堆恢复", "剩余堆仍合法，恢复只需插回 k 个订单", "F5 命题 1；PAMS Market；Python heapq",
"A 用 n 代表扫描前的订单数，用 k 代表暂取后要恢复的订单数。heappop 维护剩余堆。相同对象集合、确定性的优先键以及顺序成交保证逻辑出堆一致。数组形状可以不同。");
rows(s,[["恢复方法","工作量","所需条件"],["stock heapify","O(n)","恢复后重建整个堆"],["逐条 heappush","O(k log n) 比较","剩余堆合法，比较键保持"]],[4.0,3.55,4.09],{height:.83});
callout(s,"相同订单集合与优先级给出相同的逻辑出堆序列。");

const heapCsv = fs.readFileSync(path.join(evidence, "T07/derived/pilot-heap-work.csv"),"utf8").trim().split(/\r?\n/);
const header = heapCsv.shift().split(",");
const heap = heapCsv.map(line=>Object.fromEntries(line.split(",").map((v,i)=>[header[i],v])));
const heapDeep = heap.find(r=>r.seed==="11" && r.workload==="W2-H");
const fmt = new Intl.NumberFormat("en-US");
s = slide("增量堆恢复", "深簿受益最大，浅簿仍有小幅收益", "华硕 F2 H01｜仿真速度比，五 seed 配对；右侧比较器数据为 M5 P11",
"A 先讲华硕同轨迹计时：仿真从浅簿 1.251 倍到深簿 16.956 倍，W2-H 这里是 H01 专用区组。右侧为 Apple M5 独立探针，深簿比较次数 8,245,535 降至 92,206。两类证据分别指向实际仿真和算法比较工作量。");
const heapMeasured = ["W0-H","W1-H","W2-H"].map(w=>effect("H01-"+w,"upstream","incremental"));
chart(s,"bar",[{name:"仿真速度比",labels:["W0-H","W1-H","W2-H"],values:heapMeasured.map(r=>Number(r.point))}],
  {barDir:"col",showLegend:false,showValue:true,dataLabelFormatCode:'0.00"×"',valAxisMinVal:0,valAxisMaxVal:20,valAxisMajorUnit:5});
aside(s,"深簿比较工作量", [fmt.format(heapDeep.upstream_comparisons)+" 次原版比较", fmt.format(heapDeep.incremental_comparisons)+" 次增量比较", "Apple M5 · W2-H seed 11"]);
callout(s,"W2-H 专用 H01 对照的仿真速度比为 "+interval(heapMeasured[2])+"。",6.12,{fontSize:19});

s = slide("原生数值", "原生直调承担 Python/C++ 数据边界成本", "F5 §4.3、§7.4；B 原实现 0e5bf62；华硕 E02",
"B 说明 FCN 三项共享同一标量公式。绑定检查 dtype、形状、stride 与 owner，准备结果后释放 GIL。相同增量底座上的直调在 W1-H 和 W3 均变慢，数字来自五 seed 的整机配对。");
flow(s,["Python 准备输入", "pybind11 检查", "共享 C++ FCN", "有序构造订单"],2.38);
rows(s,[["编译与 ABI","严格浮点，112 B 数值输入，16 B 输出"],["执行边界","校验和分配后释放 GIL，再执行数值区间"],["华硕整机 E02","Python / direct，W1-H "+effect("E02-W1-H","seq","native-direct").point+"×，W3 "+effect("E02-W3-LARGE-MULTI","seq","native-direct").point+"×"]],[3.29,8.35],{atY:3.55,height:.65,head:false,fontSize:19});
callout(s,"RNG 准备、packing 和订单回建仍处在仿真路径上。");

const production = granularity.production_batches.slice(0,4);
s = slide("多核与同步", "W2-H 的 256 行批次只形成两个有效 range", "T05 真实生产批次，ASUS seed 101，4 workers，static，grain 128",
"C 说明持久池省去逐批创建，提交和汇合仍存在。range 数来自真实回调。W2-H 有 14 批由一个线程完成两段、18 批由两个线程参与，只反映参与度。");
rows(s,[["负载","批次数","行 / 批","实际 range / 批"],...production.map((r,i)=>[
  ["W0-CI2002","W1-H","W2-H","W3-LARGE-MULTI"][i],[600,120,32,10][i],fmt.format(r.native_batch_width.max),r.actual_ranges.max
])],[4.55,2.20,2.28,2.61],{height:.61});
callout(s,"W2-H 的 32 批中，14 批的两个 range 都由同一线程执行。");

s = slide("多核与同步", "较大输入摊薄一次提交的固定成本", "E05 华硕同输入回放；256 行点来自 T05 独立技术补充；每点三次启动",
"C 说明纵轴为同布局 direct 时间除以四 worker。E05 同种子真实输入在 2,048、4,096、8,192 行的比值为 0.768、1.200、1.629。T05 的 256 行真单批为 0.116。8,192 行拼接 32 批，调用边界不同。");
const real256 = granularity.replay.prefixes.find(r=>r.mode==="tf4" && r.rows===256).direct_over_variant.median;
chart(s,"bar",[{name:"AoS 四 worker 的速度比",labels:["256 (T05)","2,048","4,096","8,192"],
  values:[Number(real256.toFixed(3)),...results.replay_aos_4.map(Number)]}],
  {barDir:"col",showLegend:false,showValue:true,dataLabelFormatCode:'0.000"×"',valAxisMinVal:0,valAxisMaxVal:1.8,valAxisMajorUnit:.3});
aside(s,"256 行是生产单批",["另外三点合并 8、16、32 批","含绑定、输出分配和汇合","结果摘要按输入长度核对"]);
callout(s,"8,192 行的 1.629× 对应一次合并调用。",6.12);

s = slide("多核与同步", "整机多核扩展接近或低于直调", "华硕 E02｜同增量堆和 AoS，仿真时间，五 seed × 三重复",
"C 用一 worker 对照介绍调度器开销。W1-H 四 worker 0.947，效率 23.7%；W3 四 worker 1.001，置信区间 0.990–1.010。配置线程数不是参与线程数，前页已给出实际 range。");
const scaling = ["W1-H","W3-LARGE-MULTI"].map((workload,i)=>({name:i?"W3":"W1-H",labels:["1 worker","2 workers","4 workers"],
  values:[1,2,4].map(w=>Number(effect("E02-"+workload,"native-direct","native-"+w).point))}));
chart(s,"line",scaling,{valAxisMinVal:.90,valAxisMaxVal:1.05,valAxisMajorUnit:.05,valAxisLabelFormatCode:'0.00"×"'});
aside(s,"4 worker 并行效率",["W1-H  23.7%","W3  25.0%","效率 = 相对直调速度比 / 4"]);
callout(s,"W3 四 worker 的 95% 区间跨过 1×。",6.12);

s = slide("内存层次", "SoA 尚未改善受测仿真的系统时间", "华硕 E03／W2-H 综合区组，仿真速度比；95% seed-bootstrap 区间",
"D 报告两个区间支持 AoS，另两个跨过一。E05 固定真实输入的六个 replay 匹配点，SoA 的启动中位数高 2.0%–11.2%。生产 packing 和复用缓冲单测。");
rows(s,[["同执行方式","SoA 速度比及 95% 区间"],
 ["W2-H direct",interval(effect(system,"B2","direct-soa"))],["W2-H 四 worker",interval(effect(system,"B3","B4"))],
 ["W3 direct",interval(effect("E03-W3-LARGE-MULTI","direct-aos","direct-soa"))],
 ["W3 四 worker",interval(effect("E03-W3-LARGE-MULTI","parallel-4-aos","parallel-4-soa"))]],[4.10,7.54],{height:.62});
callout(s,"E05 回放的 SoA 用时多 "+results.replay_soa_penalty_percent.join("%–")+"%。",5.76);

s = slide("内存层次", "工作集字节数限定解释，硬件计数验证范围", "华硕环境、F3 PMU 与 F5 §7.7",
"D 报告本机 L1I 32 KiB、L1D 48 KiB、L2 1 MiB、L3 16 MiB、64 B line。8,192 行时 AoS 同时活跃数组的上界 1,152 KiB，SoA 2,048 KiB。L1D alias 分别是 D-cache accesses 和 miss 触发的 L2 requests。事件范围为用户态进程及继承任务。W2-H 四 worker AoS / SoA 的 IPC 为 3.359 / 3.309。");
rows(s,[["前缀行数","输入 + 一份输出"],["2,048","256 KiB"],["4,096","512 KiB"],["8,192","1,024 KiB"]],[3.10,4.10],{height:.62});
aside(s,"ASUS 来宾 Cache",["L1I 32 KiB，L1D 48 KiB","L2 1 MiB，L3 16 MiB（共享）","Cache line 64 B"]);
text(s,"数值输入 112 B/行，输出 16 B/行。",x,4.94,7.4,.42,{fontSize:19});
callout(s,"24 次 PMU、48 个事件值覆盖率均为 100%。专用 LLC 缺测。",5.65,{fontSize:18});

s = slide("系统瓶颈", "堆恢复降下来后，决策准备依然显著", "华硕 E05 W1-H seed 101 匹配 profile；右侧为同机 W2-H 生产 profile",
"D 读图。W1-H 恢复从 13.152 秒降到 0.327 秒，Python 收集仍 1.141 秒。W2-H 四个配置的随机准备和 packing 为 666–676 毫秒，含汇合的绑定为 1.93–10.68 毫秒。同工作负载比较，包含式区段分别报告。");
chart(s,"bar",[{name:"堆恢复",labels:["原版 Python","增量 Python"],values:[13.152,.327]},
  {name:"Python 收集",labels:["原版 Python","增量 Python"],values:[1.191,1.141]}],
  {barDir:"col",valAxisMinVal:0,valAxisMaxVal:15,valAxisMajorUnit:3,valAxisLabelFormatCode:'0" s"'});
aside(s,"W2-H 阶段成本",["准备与 packing 666–676 ms","绑定加等待 1.93–10.68 ms","撮合候选收集 898–922 ms"]);
callout(s,"准备、回填、撮合分别计量，含括区间保留原范围。",6.12);

s = slide("验证与计量", "独立 stock PAMS 参考核对完整状态轨迹", "R4B x86 封存 C01/V01；F5 原件复核；E 原实现 533ab87",
"E 说清独立性来自源实现和独立进程。比较按事件序列、逐步状态、初态、最终账本、RNG；解释为什么只看价格或订单总数不足。6 对代表性复跑共 12 条，自动化同机复验。");
rows(s,[["华硕 x86","独立参考","生产候选","实际通过"],["C01","60","360","420 / 420"],["V01","20","125","145 / 145"]],[3.29,2.64,2.80,2.91],{height:.79});
callout(s,"额外六组同机对照通过。独立人员复现回执待取得。",5.44);

s = slide("验证与计量", "冻结对照完整覆盖 375 个配对", "F2/F3/F4 华硕组长授权的独立研究；原两人 G3 未生效",
"E 讲同主机、同负载、同 seed 和同区组。每个 seed 三次重复先聚合，再以五个 seed 为单位做 10,000 次 bootstrap。三种端点是同一批运行。F2 与 E05 共 606 条成功，岗位签认另记录。");
rows(s,[["实际执行","覆盖"],["低开销仿真与完整进程","465 条计时，62 条预热"],["机制测量 E05","7 条 profile，24 条 PMU，48 条 replay"],["配对有效性","375 / 375；失败、超时、缺失均为 0"]],[4.04,7.60],{height:.72});
callout(s,"区间由五个市场 seed 重采样，预热排除。");

s = slide("系统性能", "W2-H 的最大收益来自增量堆", "华硕 F4 W2-H 统一同区组直接对照｜速度比基线均为原版 PAMS",
"E 按表说明整机收益。仅增量堆在 15 个区组全部最快，仿真 16.704 倍。四 worker 的 AoS 与 SoA 仍分别为 13.266 和 13.143 倍。讲完整子进程边界，再切到功能演示。");
const total = [["只改堆 · Python","B1"],["完整 · Taskflow 4 AoS","B3"],["完整 · Taskflow 4 SoA","B4"]];
rows(s,[["W2-H 配置","仿真速度比 [95% 区间]","完整进程"],
 ...total.map(([label,key])=>[label,interval(effect(system,"B0",key)),effect(system,"B0",key,"process_wall_s").point+"×"])
],[3.98,5.28,2.38],{height:.77,fontSize:18});
callout(s,"仅增量堆在 15 个实际区组中全部用时最短。",5.78);

s = slide("现场演示", "同一 seed 的六种执行配置生成同一轨迹", "F6 华硕真实 Demo，seed 42，六配置功能复验",
"A 演示固定源、seed 和命令。展示第一笔订单、第一笔成交及最终账本/RNG 摘要。比较为 6/6。本次华硕复验包含 smoke、参考和六次候选。离线可选择已禁网复核的轨迹重放。");
rows(s,[["参考事件","数量","候选执行"],["订单",demo.oracle.counts.OrderLog,"原堆 Python、增量 Python"],["成交",demo.oracle.counts.ExecutionLog,"原生 direct AoS"],["到期",demo.oracle.counts.ExpirationLog,"Taskflow SoA，1 / 2 / 4 workers"]],[3.62,2.46,5.56],{height:.69});
callout(s,"六条候选均通过事件、逐步状态、初态、终态和完整 RNG 比较。",5.78,{fontSize:20});

s = slide("结论", "性能收益取决于剩余工作和真实任务粒度", "F5 论文与补充材料；完整方法、原始数据索引及脚本见课程交付包",
"A 或 E 总结。深簿恢复展示算法比较工作量。调度开销由实际批次和独占 range 决定。布局按运行路径和 packing 选择。把架构现象与计算机组成课程中的堆、同步、存储层次和性能归因关联起来。");
rows(s,[["计算机组成原理","CoreOrder 中的可观察现象"],["算法工作量","深簿的比较器调用显著下降"],["调度与同步","短批次提交成本占比高，大前缀 replay 出现收益"],["存储层次","同字段布局的 packing 与访存路径共同影响成本"]],[3.80,7.84],{height:.71});
callout(s,"在固定轨迹上测量工作量，再用同主机同范围的对照解释性能。",5.78,{fontSize:20});

s = slide("参考与复现", "核心结果均可回查到版本、记录和生成脚本", "公开审阅镜像 codex/r8-gpt-review；最终参考文献见 F5 正文",
"答辩结束可回到结论页。现场备查该页、论文数字审计和归档清单。");
rows(s,[["复用与理论","一手来源"],["PAMS","Hirano、Takata、Izumi，2023，arXiv:2309.10729v1"],["Taskflow","Huang 等，IEEE TPDS，2022，10.1109/TPDS.2021.3104255"],["并行上限与统计","Amdahl，1967；Kalibera 与 Jones，ISMM 2013"],["实验原件","F2、F3、F4 原始索引，F5 审计及 F6 Demo"]],[3.10,8.54],{height:.64,fontSize:18});
text(s,"github.com/DengJunxian/CoreOrder",x,5.82,11.64,.49,{fontSize:20,color:colors.teal,hyperlink:{url:"https://github.com/DengJunxian/CoreOrder"}});

const roles = [
  {role:"A", title:"市场底座、增量堆和系统集成", original:[
    ["核心实现","固定 PAMS 与公共 ABI，接入增量堆和安全前缀"],
    ["后续集成","接入四种观测模式、正式执行与目标机流式验收"],
    ["证据锚点","614dacf、da29dd6、92f8bbf；集成 58ec576"]],
   proof:"恢复比较量随簿深和暂取比例变化", observed:[
    ["M5 W2-H，seed 11","8,245,535 → 92,206 次比较调用"],
    ["逻辑轨迹","相同对象、确定性优先级和原成交顺序"],
    ["现场 Demo","seed 42，89 单与 28 成交，六配置轨迹一致"]]},
  {role:"B", title:"FCN 数值核和 Python/C++ 边界", original:[
    ["核心实现","共享 FCN 标量公式，direct 路径及 range 路径"],
    ["运行边界","检查 dtype 与 stride，保留 owner，GIL 外求值"],
    ["证据锚点","0e5bf62、原分支 f8d2be9，接收 4667b96"]],
   proof:"原生 direct 是区分语言开销的重要对照", observed:[
    ["严格浮点","固定表达式，关闭 fast-math 和浮点收缩"],
    ["共同 ABI","112 B 数值输入，16 B 结果"],
    ["华硕整机 E02","W1-H 与 W3 的 Python / direct 为 0.860×、0.856×"]]},
  {role:"C", title:"持久执行器、任务粒度和汇合", original:[
    ["核心实现","Taskflow 持久执行器，按半开行范围调度"],
    ["确定性","每范围写独占输出，汇合后按原序回填"],
    ["证据锚点","e615358、cfe9877；接收 b3e8560"]],
   proof:"真实任务粒度限定可用并行度", observed:[
    ["W2-H 生产批","256 行，两个有效 range，14/32 批由单线程执行"],
    ["四 worker replay","256 行 0.116×（T05）；8,192 行 1.629×（E05）"],
    ["仿真并行效率","W1-H 23.7%，W3 25.0%，各用同布局 direct 基线"]]},
  {role:"D", title:"实时 packing、布局缓冲与 Cache 观测", original:[
    ["核心实现","AoS/SoA 同字段缓冲、只读租用与事件变参刷新"],
    ["生产 packing","按目标布局直接打包，复用缓冲容量"],
    ["证据锚点","a56e485、3ef2298；接收 8b63c8c"]],
   proof:"布局开销同时发生在准备和消费端", observed:[
    ["六个 E05 匹配点","SoA 回放用时多 2.0%–11.2%，固定输出摘要"],
    ["8,192 行 replay","名义 1,024 KiB，SoA 存活数组上界 2,048 KiB"],
    ["Cache 范围","全部 48 个事件计数覆盖 100%，专用 LLC 缺测"]]},
  {role:"E", title:"独立比较器、原始回执与实验契约", original:[
    ["核心实现","stock PAMS 独立参考、有序观察、首差定位和故障注入"],
    ["贡献归属","E 实现验证与协议原型，A 后续接入生产执行入口"],
    ["证据锚点","533ab87、原分支 b05d555，接收 5eb8690"]],
   proof:"可比较结果来自可追踪的工作量和回执", observed:[
    ["正确性矩阵","C01 420/420，V01 145/145"],
    ["统计独立单位","五个市场 seed，每 seed 三次同区组技术重复"],
    ["实际计量","组长独立授权，375/375 有效配对；原 G3 待签"]]},
];
function personal(ppt, r) {
  const a = shell(ppt,{section:"成员 "+r.role+" ／ 贡献",title:r.title,source:"原提交与接收映射见 CONTRIBUTIONS.md 及论文补充材料",notes:"第一张讲原始实现和整机接入的责任边界。"});
  rows(a,[["贡献","可核交付"],...r.original],[3.05,8.59],{height:.79,fontSize:20});
  const b = shell(ppt,{section:"成员 "+r.role+" ／ 证据",title:r.proof,source:"证据出处和两页讲稿见 DEFENSE.md 与 F5 论文审计",notes:"第二张讲指标范围、实际发现和限制。"});
  rows(b,[["证据","现场说明"],...r.observed],[3.58,8.06],{height:.79,fontSize:20});
}
async function write() {
  await main.writeFile({fileName:path.join(here,"CoreOrder-Defense.pptx")});
  const appendix = deck("CoreOrder｜五人贡献与答辩附页");
  for (const r of roles) personal(appendix,r);
  await appendix.writeFile({fileName:path.join(here,"CoreOrder-Contributions.pptx")});
}
write().catch(error=>{ console.error(error); process.exitCode=1; });
