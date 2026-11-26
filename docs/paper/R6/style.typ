#let ink = rgb("#172a3e")
#let muted = rgb("#40586e")
#let rule = rgb("#ccd7df")

#let manuscript(doc-title, short-title, body) = {
  set document(title: doc-title, author: "Parallel team")
  set page(
    paper: "a4",
    margin: (top: 24mm, bottom: 22mm, x: 26mm),
    header: context {
      if counter(page).get().first() > 1 {
        text(font: ("Helvetica", "New Computer Modern"), size: 8pt, fill: muted, short-title)
        v(3pt)
        line(length: 100%, stroke: .5pt + rule)
      }
    },
    numbering: "1",
  )
  set text(font: "Libertinus Serif", size: 11pt, lang: "en", fill: ink)
  set par(justify: true, leading: .63em, spacing: 1em)
  set heading(numbering: "1.1")
  show heading: set text(font: ("Helvetica", "New Computer Modern"), fill: ink)
  show figure.caption: set text(size: 9.4pt)
  show figure.caption: set par(justify: false)
  show math.equation.where(block: true): set align(center)
  set table(
    stroke: (x, y) => (bottom: .5pt + rule),
    inset: (x: 7pt, y: 6pt),
    fill: (x, y) => if y == 0 { rgb("#e9f0f4") } else { none },
  )
  show table: set text(size: 9.6pt)
  show table: set par(justify: false)
  show table.cell.where(y: 0): set text(weight: "semibold")
  body
}

#let paper-title(title, subtitle) = {
  block(below: 14pt)[
    #set par(justify: false)
    #set text(hyphenate: false)
    #text(font: ("Helvetica", "New Computer Modern"), size: 20.5pt, weight: "bold", fill: ink, title)
    #v(9pt)
    #text(font: ("Helvetica", "New Computer Modern"), size: 10pt, fill: muted, subtitle)
  ]
}
