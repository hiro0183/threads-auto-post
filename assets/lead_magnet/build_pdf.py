# -*- coding: utf-8 -*-
"""
院長の時間 棚卸しシート - PDF生成スクリプト (reportlab)
実行: PYTHONIOENCODING=utf-8 python build_pdf.py
"""
import os
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak, Frame, PageTemplate, BaseDocTemplate
)
from reportlab.platypus.flowables import Flowable
from reportlab.lib.styles import ParagraphStyle

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PDF = os.path.join(HERE, "tanaoroshi_sheet.pdf")

# ---------- フォント登録 (Yu Gothic) ----------
FONT_DIR = r"C:\Windows\Fonts"
pdfmetrics.registerFont(TTFont("YuGoR", os.path.join(FONT_DIR, "YuGothR.ttc")))
pdfmetrics.registerFont(TTFont("YuGoM", os.path.join(FONT_DIR, "YuGothM.ttc")))
pdfmetrics.registerFont(TTFont("YuGoB", os.path.join(FONT_DIR, "YuGothB.ttc")))

INK = colors.HexColor("#2a2622")
SUB = colors.HexColor("#5c584f")
ACCENT = colors.HexColor("#1f4b3f")
ACCENT_SOFT = colors.HexColor("#e7efe9")
LINE = colors.HexColor("#cfc9ba")
LINE_SOFT = colors.HexColor("#e3ddce")
PAPER = colors.HexColor("#faf7f0")
WHITE = colors.white

styles = {
    "kicker": ParagraphStyle("kicker", fontName="YuGoB", fontSize=9, leading=11,
                              textColor=ACCENT, spaceAfter=4),
    "h1": ParagraphStyle("h1", fontName="YuGoB", fontSize=22, leading=28,
                          textColor=INK, spaceAfter=4),
    "subtitle": ParagraphStyle("subtitle", fontName="YuGoR", fontSize=11, leading=16,
                                textColor=SUB, spaceAfter=8),
    "byline": ParagraphStyle("byline", fontName="YuGoR", fontSize=9, leading=15,
                              textColor=SUB),
    "sectiontitle": ParagraphStyle("sectiontitle", fontName="YuGoB", fontSize=12.5,
                                    leading=16, textColor=ACCENT, spaceBefore=4, spaceAfter=6),
    "core": ParagraphStyle("core", fontName="YuGoM", fontSize=10.5, leading=19,
                            textColor=INK, leftIndent=4),
    "step": ParagraphStyle("step", fontName="YuGoR", fontSize=9.3, leading=15,
                            textColor=INK),
    "quote": ParagraphStyle("quote", fontName="YuGoR", fontSize=9, leading=15.5,
                             textColor=INK),
    "quotesrc": ParagraphStyle("quotesrc", fontName="YuGoR", fontSize=8, leading=12,
                                textColor=SUB, spaceBefore=2),
    "th": ParagraphStyle("th", fontName="YuGoB", fontSize=8.3, leading=11,
                          textColor=WHITE, alignment=TA_CENTER),
    "check": ParagraphStyle("check", fontName="YuGoR", fontSize=8.5, leading=13,
                             textColor=INK),
    "dt": ParagraphStyle("dt", fontName="YuGoB", fontSize=9, leading=12, spaceBefore=4,
                          textColor=ACCENT),
    "dd": ParagraphStyle("dd", fontName="YuGoR", fontSize=8.5, leading=12.5,
                          textColor=INK, spaceAfter=1),
    "cta_lead": ParagraphStyle("cta_lead", fontName="YuGoR", fontSize=8.5, leading=11,
                                textColor=WHITE, alignment=TA_CENTER),
    "cta_main": ParagraphStyle("cta_main", fontName="YuGoB", fontSize=11.5, leading=16,
                                textColor=WHITE, alignment=TA_CENTER, spaceBefore=3, spaceAfter=4),
    "cta_note": ParagraphStyle("cta_note", fontName="YuGoR", fontSize=8.2, leading=12.5,
                                textColor=WHITE, alignment=TA_CENTER, spaceAfter=6),
    "cta_url": ParagraphStyle("cta_url", fontName="YuGoR", fontSize=7.3, leading=10,
                               textColor=WHITE, alignment=TA_CENTER, spaceBefore=5),
    "footer": ParagraphStyle("footer", fontName="YuGoR", fontSize=8, leading=11,
                              textColor=SUB),
    "footer_b": ParagraphStyle("footer_b", fontName="YuGoB", fontSize=8, leading=11,
                                textColor=ACCENT),
}


class ColorBox(Flowable):
    """背景色つきの箱の中に別の flowable(テーブル1セル的に使う) を置くための簡易ラッパー"""
    pass


def hr(color=LINE, thickness=0.6, space_before=4, space_after=8):
    return HRFlowable(width="100%", thickness=thickness, color=color,
                       spaceBefore=space_before, spaceAfter=space_after)


def build_story():
    story = []

    # ---------- header ----------
    story.append(Paragraph("FREE WORKSHEET", styles["kicker"]))
    story.append(Paragraph("院長の時間　棚卸しシート", styles["h1"]))
    story.append(Paragraph("1日2時間をつくるための、「院長がやらなくていい仕事」の見つけ方", styles["subtitle"]))

    byline_tbl = Table(
        [[Paragraph(
            "作成：<b>ヒロ先生</b>（一人整体院14年・47歳）／単価35,000円（施術20分）／週休3日／"
            "月商は300を切ったことがありません。今年の夏は10連休を取りましたが、売上は保てました。",
            styles["byline"])]],
        colWidths=[170 * mm],
    )
    byline_tbl.setStyle(TableStyle([
        ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(byline_tbl)
    story.append(Spacer(1, 12))

    # ---------- section 1 ----------
    story.append(Paragraph("① まずこれだけ", styles["sectiontitle"]))
    core_items = [
        "足りないのは、努力でも根性でもありません。",
        "一番の詰まりは、たいてい「自分がやった方が早いから」です。",
        "だから、まずは書き出して、分けるところから始めます。",
    ]
    core_html = "<br/>".join(f"{i+1}．{t}" for i, t in enumerate(core_items))
    core_tbl = Table([[Paragraph(core_html, styles["core"])]], colWidths=[170 * mm])
    core_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(core_tbl)
    story.append(Spacer(1, 14))

    # ---------- section 2 ----------
    story.append(Paragraph("② 使い方　3ステップ", styles["sectiontitle"]))
    steps = [
        "昨日1日の仕事を、時刻つきで全部書き出します。施術も事務も、5分で終わることも省かずに書きます。",
        "書き出したものを1つずつ、3つに分けます。<br/>"
        "<b>残す</b>＝院長にしかできないこと　<b>渡す</b>＝人か仕組みに任せられること　<b>やめる</b>＝やめても何も起きないこと",
        "「渡す」「やめる」の中から<b>1つだけ</b>選び、<b>いつまでにやるか</b>を書きます。期限を切らない気づきは、成果になりません。",
    ]
    step_rows = []
    for i, s in enumerate(steps, start=1):
        step_rows.append([Paragraph(str(i), ParagraphStyle(
            "stepnum", fontName="YuGoB", fontSize=11, leading=13,
            textColor=ACCENT, alignment=TA_CENTER)), Paragraph(s, styles["step"])])
    step_tbl = Table(step_rows, colWidths=[10 * mm, 160 * mm])
    step_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, LINE_SOFT),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(step_tbl)
    story.append(Spacer(1, 8))

    quote_html = (
        "ノートは綺麗で気づきも多いのに成果が出ない人は、いつまでにやるという期限を切っていません。<br/>"
        "1日15分は、1日の1%です。15分積めば1.01、サボれば0.99。365日続けると、37.8倍の差になります。"
    )
    quote_tbl = Table(
        [[Paragraph(quote_html, styles["quote"])],
         [Paragraph("— ヒロ先生の講義より", styles["quotesrc"])]],
        colWidths=[170 * mm])
    quote_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), WHITE),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 1), (-1, 1), 0),
    ]))
    story.append(quote_tbl)
    story.append(Spacer(1, 10))

    # ---------- section 3: table ----------
    story.append(Paragraph("③ シート本体（昨日1日を書き出す）", styles["sectiontitle"]))
    header = [Paragraph(h, styles["th"]) for h in
              ["時刻", "やったこと", "かかった時間", "残す・渡す・やめる", "メモ"]]
    rows = [header]
    for _ in range(10):
        rwc_cell = Paragraph(
            '残<font color="white">.</font>○　渡<font color="white">.</font>○　や<font color="white">.</font>○',
            ParagraphStyle("rwc", fontName="YuGoR", fontSize=7.5, leading=10,
                           textColor=SUB, alignment=TA_CENTER))
        rows.append(["", "", "", rwc_cell, ""])
    col_w = [18 * mm, 46 * mm, 20 * mm, 46 * mm, 40 * mm]
    sheet_tbl = Table(rows, colWidths=col_w, repeatRows=1, rowHeights=[7.5 * mm] + [7.6 * mm] * 10)
    sheet_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(sheet_tbl)
    story.append(Spacer(1, 8))

    # ---------- section 4: checklist ----------
    story.append(Paragraph("④ 「渡す」候補チェック", styles["sectiontitle"]))
    items = [
        "予約リマインドの連絡", "予約変更・キャンセル待ちの連絡", "口コミへの返信の下書き",
        "SNS投稿の下書き", "ブログの下書き", "HPの更新", "カルテの整理・清書",
        "問診票の入力", "月の数字の集計", "領収書・請求書の整理", "物販の在庫確認と発注",
        "備品の発注", "清掃", "写真の整理", "チラシ・POPづくり", "広告の運用",
        "求人文の作成", "LINEの定型の返信", "セミナー・勉強会の申込み手続き", "施術中の電話対応",
    ]
    half = (len(items) + 1) // 2
    left_items, right_items = items[:half], items[half:]
    check_rows = []
    for i in range(max(len(left_items), len(right_items))):
        left = f"□ {left_items[i]}" if i < len(left_items) else ""
        right = f"□ {right_items[i]}" if i < len(right_items) else ""
        check_rows.append([Paragraph(left, styles["check"]), Paragraph(right, styles["check"])])
    check_tbl = Table(check_rows, colWidths=[85 * mm, 85 * mm])
    check_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 0.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(check_tbl)
    story.append(Spacer(1, 8))

    # ---------- section 5: example ----------
    example_flow = []
    pairs = [
        ("渡した", "投稿の下書きと数字の分析（週3日・4〜5時間かかっていたものが、30分〜1時間に）、"
                 "予約リマインドの文章づくり、LINE返信の下書き、カルテ整理。パソコンはもともと苦手でしたが、"
                 "事務にかかる時間は月40時間減りました。"),
        ("やめた", "広告を自分で打つのをやめ、同じ予算で人に任せました。リスティング広告は一切やめましたが、"
                  "結果、困ったことは何もありませんでした。"),
        ("残した", "施術と問診、そして経営を考える朝の時間（一番コンディションのいい寝起きの時間）。"),
        ("決めた", "施術中に電話に出ないこと。受付スタッフが急に休んだ日、施術中に自分で電話を取ったことがあり、"
                  "そのとき「施術中に電話に出ること自体が信頼を削る」と気づいたからです。"),
    ]
    for label, text in pairs:
        example_flow.append(Paragraph(label, styles["dt"]))
        example_flow.append(Paragraph(text, styles["dd"]))
    ex_tbl = Table([[example_flow]], colWidths=[170 * mm])
    ex_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
    ]))
    story.append(KeepTogether([Paragraph("⑤ 僕の場合", styles["sectiontitle"]), ex_tbl]))
    story.append(Spacer(1, 8))

    # ---------- section 6: CTA ----------
    cta_flow = [
        Paragraph("埋めたシートを持って", styles["cta_lead"]),
        Paragraph("無料の経営の問診（Zoom30分・内容により最大60分）へ", styles["cta_main"]),
        Paragraph(
            "どの仕事から手放すと一番ラクになるかを、一緒に見ます。売り込みはしません。<br/>"
            "「うちはまだ早い」も、立派な答えです。",
            styles["cta_note"]),
        Paragraph(
            "▶ LINEで経営の問診に申し込む",
            ParagraphStyle("ctabtn", fontName="YuGoB", fontSize=10.5, leading=14,
                           textColor=ACCENT, alignment=TA_CENTER, backColor=WHITE)),
        Paragraph(
            "https://utage-system.com/line/open/QBooAfM2qWKZ?mtid=uVqmOIrsLg8j",
            styles["cta_url"]),
    ]
    cta_tbl = Table([[cta_flow]], colWidths=[170 * mm])
    cta_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(KeepTogether([Paragraph("⑥ 次の一歩", styles["sectiontitle"]), cta_tbl]))

    return story


def draw_footer(canvas, doc):
    """全ページ共通のフッター（実際に発生したページ数に合わせて自動描画）"""
    canvas.saveState()
    left = doc.leftMargin
    right = A4[0] - doc.rightMargin
    y = 7 * mm
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.6)
    canvas.line(left, y + 4 * mm, right, y + 4 * mm)
    canvas.setFont("YuGoB", 8)
    canvas.setFillColor(ACCENT)
    canvas.drawString(left, y, "ヒロ先生")
    label_w = canvas.stringWidth("ヒロ先生", "YuGoB", 8)
    canvas.setFont("YuGoR", 8)
    canvas.setFillColor(SUB)
    canvas.drawString(left + label_w, y, "｜院長を現場から解放する仕掛け人")
    canvas.drawRightString(right, y, f"{canvas.getPageNumber()} / 2")
    canvas.restoreState()


def main():
    doc = SimpleDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=16 * mm, rightMargin=16 * mm,
        topMargin=11 * mm, bottomMargin=17 * mm,
        title="院長の時間 棚卸しシート",
        author="ヒロ先生",
    )
    story = build_story()
    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    print(f"PDF written: {OUT_PDF}")


if __name__ == "__main__":
    main()
