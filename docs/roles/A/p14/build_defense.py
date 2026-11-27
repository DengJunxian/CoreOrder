"""Generate the two editable member-A slides with the repo figures."""

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Inches, Pt


ROOT = Path(__file__).resolve().parent
NAVY = "132F4B"
GREEN = "006E60"
SLATE = "40556B"
RULE = "DCE6ED"
FONT = "Noto Sans CJK SC"


def text(slide, x, y, width, height, value, size, color=NAVY, bold=False):
    frame = slide.shapes.add_textbox(*(Inches(n) for n in (x, y, width, height))).text_frame
    frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
    frame.word_wrap = True
    frame.vertical_anchor = MSO_ANCHOR.TOP
    paragraph = frame.paragraphs[0]
    paragraph.line_spacing = 1.13
    run = paragraph.add_run()
    run.text = value
    run.font.name = FONT
    east_asian = OxmlElement("a:ea")
    east_asian.set("typeface", FONT)
    run._r.get_or_add_rPr().append(east_asian)
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color)


def line(slide, x, y, width, height, color=RULE):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, *(Inches(n) for n in (x, y, width, height)))
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor.from_string(color)
    shape.line.fill.background()
    shape.shadow.inherit = False


def page(deck, title, subtitle, footer):
    slide = deck.slides.add_slide(deck.slide_layouts[6])
    text(slide, .62, .42, 12, .25, "CoreOrder   /   成员 A", 13, GREEN, True)
    text(slide, .62, .85, 12, .6, title, 32, bold=True)
    text(slide, .62, 1.55, 12, .48, subtitle, 16, SLATE)
    line(slide, .62, 2.02, 12.05, .018)
    line(slide, 9.05, 2.33, .018, 4.15)
    line(slide, .62, 6.91, 12.05, .018)
    text(slide, .62, 7.04, 12, .27, footer, 10, SLATE)
    return slide


def point(slide, y, title, body):
    text(slide, 9.35, y, 3.3, .36, title, 17, GREEN, True)
    text(slide, 9.35, y + .43, 3.3, .83, body, 15, SLATE)


def build():
    deck = Presentation()
    deck.slide_width, deck.slide_height = Inches(13.333), Inches(7.5)
    deck.core_properties.title = "CoreOrder 成员 A · 个人贡献答辩"
    deck.core_properties.author = "CoreOrder 成员 A"
    one = page(
        deck, "复用原市场，保留执行顺序",
        "固定 PAMS 作为原版参考，在普通 FCN 采集和订单堆恢复处进行局部改动。",
        "固定 PAMS 6cd5381   /   候选生产代码 92f8bbf   /   流程图中绿色为成员 A 的局部适配",
    )
    one.shapes.add_picture(str(ROOT / "figures/execution-dataflow.png"),
                           Inches(.72), Inches(2.55), width=Inches(8.13))
    text(one, .72, 6.07, 8.1, .62, "订单重建后，PAMS 继续抽样、提交、插入 HFT、撮合并更新账户。",
         15, SLATE)
    point(one, 2.37, "固定基准", "沿用 PAMS 的策略、市场、事件、撮合与账户规则。")
    point(one, 3.78, "安全批次", "批宽受剩余非空代理名额约束，空结果按原排列补批。")
    point(one, 5.18, "独立差分", "按原调用顺序取随机数和回建订单，用 E 的工具比较事件、状态与 RNG。")
    one.notes_slide.notes_text_frame.text = (
        "约 55 秒。先解释为何选择有可运行参考的 PAMS。沿图说明候选前缀、原 Gaussian 调用、"
        "独占输出和汇合、按序回建。B、C、D 的模块由对应成员提供。E 以独立原版 PAMS 比较。"
    )

    two = page(
        deck, "深簿小暂取时，恢复比较更少",
        "从仍合法的双侧余堆出发，逐项压回原对象。配对与统一价在恢复前已经确定。",
        "P11 本机诊断   /   Apple M5，macOS arm64，seed 11、29   /   正式 H01、E05 未运行",
    )
    chart = ROOT.parent / "evidence/P13/figures/heap-mechanism-pilot.png"
    two.shapes.add_picture(str(chart), Inches(.66), Inches(2.17), width=Inches(8.28))
    point(two, 2.35, "W2-H · seed 11", "买卖深度中位数 925 / 812，暂取量中位数均为 2。")
    text(two, 9.35, 3.65, 3.3, .37, "恢复段比较次数", 17, GREEN, True)
    text(two, 9.35, 4.07, 3.3, .51, "8,245,535 → 92,206", 21, NAVY, True)
    point(two, 5.02, "剩余串行成本", "W1-H 增量后的代理抽样约占该次 cProfile 的 32%。")
    two.notes_slide.notes_text_frame.text = (
        "约 55 秒。说明统一价已在收集阶段确定，堆数组结构差异不会改变唯一最优根。"
        "图左是双侧比例和尾部，图右是比较次数。指出诊断与正式计时隔离，PMU 尚无数据。"
    )
    deck.save(ROOT / "A-defense.pptx")


if __name__ == "__main__":
    build()
